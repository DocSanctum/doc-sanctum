import json
from typing import Any

from sqlalchemy import text

from ...core.database import async_session_factory
from ...keywordindex import client as keyword_client
from ...models.source import Source


async def _search_source(
    source: Source, query: str
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Search this source's already-indexed content for query (FR-001, FR-004,
    011-keyword-search-fts) — no live access to the source (filesystem/remote
    API) happens here; all matching is against the keyword index built by
    vectorstore/indexer.py, so there's no "live fetch failed" warning case
    anymore (contracts/search-contract.md)."""
    hits = await keyword_client.query([source.id], query)
    for hit in hits:
        hit["source_name"] = source.name
    return hits, None


async def search_documents_handler(query: str, source_id: str | None = None) -> str:
    """Search documents (Markdown or PDF) for a keyword and return matching lines with context.

    Args:
        query: Search keyword (case-insensitive substring match).
        source_id: Optional source UUID to limit search scope.
    """
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
    all_matches: list[dict[str, Any]] = []
    all_warnings: list[dict[str, Any]] = []

    for source in sources:
        matches, warning = await _search_source(source, query)
        all_matches.extend(matches)
        if warning:
            all_warnings.append(warning)

    return json.dumps(
        {"query": query, "matches": all_matches, "warnings": all_warnings},
        ensure_ascii=False,
    )
