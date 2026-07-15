import json
from typing import Any

from sqlalchemy import text

from ...core.database import async_session_factory
from ...models.source import Source
from ...services.document_access import read_with_cache


async def read_document_handler(source_id: str, path: str) -> str:
    """Read the full content of a specific MD file.

    Args:
        source_id: UUID of the source containing the file.
        path: Relative file path from the source root (e.g. guide/intro.md).
    """
    async with async_session_factory() as session:
        row = (
            (
                await session.execute(
                    text("SELECT * FROM source WHERE id = :id"), {"id": source_id}
                )
            )
            .mappings()
            .first()
        )

    if not row:
        raise ValueError(f"Source not found: {source_id}")

    source = Source.from_row(dict(row))
    content, warning = await read_with_cache(source, path)

    result: dict[str, Any] = {
        "path": path,
        "source_id": source.id,
        "source_name": source.name,
        "content": content,
    }
    if warning:
        result["warning"] = warning
    return json.dumps(result, ensure_ascii=False)
