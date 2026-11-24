"""Which documents of a source failed to index, and why, so the tree can
flag them instead of only showing one count on the source.

A row exists only while the document keeps failing: a later successful
index, or the file disappearing, removes it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from sqlalchemy import text

from ..core.database import async_session_factory
from ..services.document_formats import NoExtractableTextError

logger = logging.getLogger(__name__)

ErrorKind = Literal["no_text", "fetch_failed", "index_failed"]


def classify(exc: BaseException) -> ErrorKind:
    """Map an indexing exception to a reason the UI can explain in words."""
    if isinstance(exc, NoExtractableTextError):
        return "no_text"
    if isinstance(exc, (httpx.HTTPError, OSError, ValueError)):
        return "fetch_failed"
    return "index_failed"


async def _run(sql: str, params: dict[str, Any]) -> None:
    # This only feeds a UI hint, so a failed write must not stop indexing.
    try:
        async with async_session_factory() as session:
            await session.execute(text(sql), params)
            await session.commit()
    except Exception:
        logger.warning("Could not update the document index errors", exc_info=True)


async def record(source_id: str, path: str, kind: str, message: str) -> None:
    await _run(
        "INSERT INTO doc_index_error (source_id, path, kind, message, updated_at) "
        "VALUES (:s, :p, :k, :m, :t) ON CONFLICT(source_id, path) DO UPDATE SET "
        "kind = excluded.kind, message = excluded.message, updated_at = excluded.updated_at",
        {
            "s": source_id,
            "p": path,
            "k": kind,
            "m": message[:500],
            "t": datetime.now(timezone.utc).isoformat(),
        },
    )


async def clear(source_id: str, path: str) -> None:
    await _run(
        "DELETE FROM doc_index_error WHERE source_id = :s AND path = :p",
        {"s": source_id, "p": path},
    )


async def clear_source(source_id: str) -> None:
    await _run("DELETE FROM doc_index_error WHERE source_id = :s", {"s": source_id})


async def prune(source_id: str, current_paths: set[str]) -> None:
    """Drop errors for documents that are no longer in the source."""
    try:
        stale = [
            row["path"]
            for row in await list_for_source(source_id)
            if row["path"] not in current_paths
        ]
    except Exception:
        logger.warning("Could not read the document index errors", exc_info=True)
        return
    for path in stale:
        await clear(source_id, path)


async def list_for_source(source_id: str) -> list[dict[str, Any]]:
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT path, kind, message, updated_at FROM doc_index_error "
                    "WHERE source_id = :s ORDER BY path"
                ),
                {"s": source_id},
            )
        ).mappings()
        return [dict(r) for r in rows]
