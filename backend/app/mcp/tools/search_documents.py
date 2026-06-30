import asyncio
import json
from typing import Any

from sqlalchemy import text

from ...core.database import async_session_factory
from ...models.source import Source
from .list_documents import _flatten_tree, _get_tree_with_cache
from .read_document import _read_github, _read_http, _read_local

MAX_MATCHES_PER_FILE = 10
CONTEXT_LINES = 2


def _search_lines(lines: list[str], query: str) -> list[dict[str, Any]]:
    q = query.lower()
    matches = []
    for i, line in enumerate(lines):
        if q in line.lower():
            start = max(0, i - CONTEXT_LINES)
            end = min(len(lines), i + CONTEXT_LINES + 1)
            matches.append(
                {
                    "line_number": i + 1,
                    "line": line.rstrip("\n"),
                    "context": [ln.rstrip("\n") for ln in lines[start:end]],
                }
            )
            if len(matches) >= MAX_MATCHES_PER_FILE:
                break
    return matches


async def _read_content(source: Source, path: str) -> str | None:
    try:
        if source.type == "local":
            return await _read_local(source, path)
        elif source.type == "github":
            return await _read_github(source, path)
        else:
            return await _read_http(source, path)
    except Exception:
        return None


async def _search_source(
    source: Source, query: str
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    tree, warning = await _get_tree_with_cache(source)
    doc_infos: list[dict[str, Any]] = []
    if tree and tree.get("root"):
        _flatten_tree(tree["root"], doc_infos, source)

    async def search_file(doc: dict[str, Any]) -> list[dict[str, Any]]:
        content = await _read_content(source, doc["path"])
        if content is None:
            return []
        lines = content.splitlines(keepends=True)
        hits = _search_lines(lines, query)
        for hit in hits:
            hit["path"] = doc["path"]
            hit["source_id"] = source.id
            hit["source_name"] = source.name
        return hits

    results = await asyncio.gather(*[search_file(d) for d in doc_infos])
    matches = [hit for file_hits in results for hit in file_hits]
    return matches, warning


async def search_documents_handler(query: str, source_id: str | None = None) -> str:
    """Search MD files for a keyword and return matching lines with context.

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
