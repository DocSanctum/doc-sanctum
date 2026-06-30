from typing import Any

import httpx
from sqlalchemy import text

from ...core.database import async_session_factory
from ...models.source import Source
from ...services.tree_builder import build_local_tree, build_remote_tree
from ..cache import get_cached, mark_stale, set_cached


def _flatten_tree(node: dict[str, Any], results: list[dict[str, Any]], source: Source) -> None:
    if not node.get("is_dir"):
        results.append({
            "path": node["path"],
            "name": node["name"],
            "source_id": source.id,
            "source_name": source.name,
            "source_type": source.type,
        })
        return
    for child in node.get("children", []):
        _flatten_tree(child, results, source)


async def _get_tree_with_cache(source: Source) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Returns (tree, warning_or_None)."""
    if source.type == "local":
        return build_local_tree(source), None

    cached = get_cached(source.id)
    if cached is not None and not cached["stale"]:
        return cached["data"], None

    try:
        tree = await build_remote_tree(source)
        set_cached(source.id, tree)
        return tree, None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (403, 429):
            mark_stale(source.id)
            stale = get_cached(source.id)
            warning = {
                "source_id": source.id,
                "source_name": source.name,
                "reason": "rate_limit",
                "message": f"GitHub API rate limit exceeded. Serving cached data.",
                "stale": True,
            }
            if stale:
                return stale["data"], warning
        warning = {
            "source_id": source.id,
            "source_name": source.name,
            "reason": "access_error",
            "message": str(exc),
            "stale": False,
        }
        return {"source_id": source.id, "root": {"is_dir": True, "children": []}}, warning
    except Exception as exc:
        warning = {
            "source_id": source.id,
            "source_name": source.name,
            "reason": "access_error",
            "message": str(exc),
            "stale": False,
        }
        return {"source_id": source.id, "root": {"is_dir": True, "children": []}}, warning


async def list_documents_handler(source_id: str | None = None) -> str:
    """List MD files from registered sources.

    Args:
        source_id: Optional source UUID to filter. Returns all sources if omitted.
    """
    import json

    async with async_session_factory() as session:
        if source_id:
            rows = (
                await session.execute(
                    text("SELECT * FROM source WHERE id = :id"), {"id": source_id}
                )
            ).mappings().all()
        else:
            rows = (
                await session.execute(text("SELECT * FROM source"))
            ).mappings().all()

    if source_id and not rows:
        raise ValueError(f"Source not found: {source_id}")

    sources = [Source.from_row(dict(r)) for r in rows]
    documents: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for source in sources:
        tree, warning = await _get_tree_with_cache(source)
        if warning:
            warnings.append(warning)
        if tree and tree.get("root"):
            _flatten_tree(tree["root"], documents, source)

    return json.dumps({"documents": documents, "warnings": warnings}, ensure_ascii=False)
