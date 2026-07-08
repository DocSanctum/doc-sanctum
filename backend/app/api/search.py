from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import async_session_factory
from ..mcp.tools.search_documents import _search_source
from ..mcp.tools.semantic_search_documents import DEFAULT_TOP_K
from ..models.source import Source
from ..vectorstore import client as vector_client

router = APIRouter(tags=["search"])


async def _load_sources(session: AsyncSession, source_id: str | None) -> list[Source]:
    """Shared by both /search and /semantic-search: load either a single
    source by id (404 if missing) or every registered source."""
    if source_id:
        rows = (
            (
                await session.execute(
                    text("SELECT * FROM source WHERE id = :id"), {"id": source_id}
                )
            )
            .mappings()
            .all()
        )
        if not rows:
            raise HTTPException(
                status_code=404, detail=f"Source not found: {source_id}"
            )
    else:
        rows = (await session.execute(text("SELECT * FROM source"))).mappings().all()
    return [Source.from_row(dict(r)) for r in rows]


class SearchMatch(BaseModel):
    source_id: str
    source_name: str
    path: str
    line_number: int
    line: str
    context: list[str]


class SearchWarning(BaseModel):
    source_id: str | None = None
    source_name: str | None = None
    reason: str | None = None
    message: str


class SearchResponse(BaseModel):
    query: str
    matches: list[SearchMatch]
    warnings: list[SearchWarning]


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    source_id: str | None = None,
) -> SearchResponse:
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query must not be blank")

    async with async_session_factory() as session:
        sources = await _load_sources(session, source_id)

    all_matches: list[dict[str, Any]] = []
    all_warnings: list[dict[str, Any]] = []

    for source in sources:
        matches, warning = await _search_source(source, q)
        all_matches.extend(matches)
        if warning:
            all_warnings.append(warning)

    return SearchResponse(
        query=q,
        matches=[SearchMatch(**m) for m in all_matches],
        warnings=[SearchWarning(**w) for w in all_warnings],
    )


class SemanticMatch(BaseModel):
    source_id: str
    source_name: str
    path: str
    chunk_index: int
    score: float
    excerpt: str


class SemanticSearchResponse(BaseModel):
    query: str
    results: list[SemanticMatch]
    warnings: list[SearchWarning]


@router.get("/semantic-search", response_model=SemanticSearchResponse)
async def semantic_search(
    q: str = Query(..., min_length=1),
    source_id: str | None = None,
    top_k: int | None = None,
) -> SemanticSearchResponse:
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query must not be blank")

    limit = top_k or DEFAULT_TOP_K

    async with async_session_factory() as session:
        sources = await _load_sources(session, source_id)

    all_hits: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not vector_client.init_engine():
        warnings.append(
            {
                "reason": "engine_unavailable",
                "message": "Local embedding engine is unavailable; semantic search returned no results.",
            }
        )
    else:
        for source in sources:
            all_hits.extend(await vector_client.query(source.id, q, limit))

    all_hits.sort(key=lambda h: h["score"], reverse=True)

    return SemanticSearchResponse(
        query=q,
        results=[SemanticMatch(**h) for h in all_hits[:limit]],
        warnings=[SearchWarning(**w) for w in warnings],
    )
