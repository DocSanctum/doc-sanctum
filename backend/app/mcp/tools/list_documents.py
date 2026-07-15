import json
from typing import Any

from sqlalchemy import text

from ...core.database import async_session_factory
from ...models.source import Source
from ...services.document_access import flatten_tree, get_tree_with_cache


async def list_documents_handler(source_id: str | None = None) -> str:
    """List MD files from registered sources.

    Args:
        source_id: Optional source UUID to filter. Returns all sources if omitted.
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
    documents: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for source in sources:
        tree, warning = await get_tree_with_cache(source)
        if warning:
            warnings.append(warning)
        if tree and tree.get("root"):
            flatten_tree(tree["root"], documents, source)

    return json.dumps(
        {"documents": documents, "warnings": warnings}, ensure_ascii=False
    )
