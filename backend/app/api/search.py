from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from ..core.database import async_session_factory
from ..mcp.tools.search_documents import _search_source
from ..models.source import Source

router = APIRouter(tags=["search"])


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
        else:
            rows = (
                (await session.execute(text("SELECT * FROM source"))).mappings().all()
            )

    if source_id and not rows:
        raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")

    sources = [Source.from_row(dict(r)) for r in rows]
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
