"""Why a source is being indexed and how far along it is, stored on the
source row so every backend replica and the sidebar see the same numbers.

The reason survives restarts until a sync finishes, so a rebuild that is
interrupted still explains itself when it resumes. The counts only exist
while a sync is running.
"""

from __future__ import annotations

import logging
import time
from typing import Literal

from sqlalchemy import text

from ..core.database import async_session_factory

IndexReason = Literal["initial", "model", "chunking", "keyword", "recovery"]

logger = logging.getLogger(__name__)

# Writing at most this often keeps a large rebuild from hammering SQLite.
_WRITE_INTERVAL_SECONDS = 1.0


async def _update(sql: str, params: dict) -> None:
    # Progress is only shown to the user, so a failed write must never stop
    # the indexing it describes.
    try:
        async with async_session_factory() as session:
            await session.execute(text(sql), params)
            await session.commit()
    except Exception:
        logger.warning("Could not record indexing progress", exc_info=True)


async def mark_reason(reason: IndexReason, source_id: str | None = None) -> None:
    """Record why the next sync re-indexes everything; None means all sources."""
    where = "" if source_id is None else " WHERE id = :id"
    await _update(
        f"UPDATE source SET index_reason = :r{where}", {"r": reason, "id": source_id}
    )


async def _write(source_id: str, done: int | None, total: int | None) -> None:
    await _update(
        "UPDATE source SET index_done = :d, index_total = :t WHERE id = :id",
        {"d": done, "t": total, "id": source_id},
    )


class ProgressReporter:
    """Counts documents through one sync and writes the totals now and then."""

    def __init__(self, source_id: str, total: int) -> None:
        self._source_id = source_id
        self._total = total
        self._done = 0
        self._last_write = 0.0

    async def start(self) -> None:
        if self._total:
            await _write(self._source_id, 0, self._total)
            self._last_write = time.monotonic()

    async def advance(self) -> None:
        self._done += 1
        now = time.monotonic()
        if self._total and now - self._last_write >= _WRITE_INTERVAL_SECONDS:
            await _write(self._source_id, self._done, self._total)
            self._last_write = now

    async def finish(self, completed: bool) -> None:
        """Clear the counts, and the reason too once the sync got through."""
        reason_sql = ", index_reason = NULL" if completed else ""
        await _update(
            f"UPDATE source SET index_done = NULL, index_total = NULL{reason_sql} "
            "WHERE id = :id",
            {"id": self._source_id},
        )
