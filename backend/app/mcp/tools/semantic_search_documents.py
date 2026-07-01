import json
from typing import Any

from sqlalchemy import text

from ...core.database import async_session_factory
from ...models.source import Source
from ...vectorstore import client

DEFAULT_TOP_K = 5


async def semantic_search_documents_handler(
    query: str, source_id: str | None = None, top_k: int | None = None
) -> str:
    """Search MD documents by semantic meaning using a natural-language query.

    Args:
        query: Natural-language search query.
        source_id: Optional source UUID to limit search scope. Searches all
            indexed sources if omitted.
        top_k: Maximum number of results to return (default 5).
    """
    limit = top_k or DEFAULT_TOP_K

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
        raise ValueError(f"Source not found: {source_id}")

    sources = [Source.from_row(dict(r)) for r in rows]

    all_hits: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not client.init_engine():
        warnings.append(
            {
                "reason": "engine_unavailable",
                "message": "Local embedding engine is unavailable; semantic search returned no results.",
            }
        )
    else:
        for source in sources:
            all_hits.extend(await client.query(source.id, query, limit))

    all_hits.sort(key=lambda h: h["score"], reverse=True)

    return json.dumps(
        {"query": query, "results": all_hits[:limit], "warnings": warnings},
        ensure_ascii=False,
    )
