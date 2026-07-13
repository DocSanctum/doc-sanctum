from __future__ import annotations

import os
import socket
from datetime import datetime, timedelta, timezone
from typing import cast

from sqlalchemy import CursorResult, text

from ..core.database import async_session_factory

# Cross-replica coordination for automatic rebuilds in multi-replica
# (scaleout) deployments — an advisory lock in the same SQLite database
# every replica already shares via the sqlite_data volume, so only one
# replica performs a given source's automatic rebuild at a time. Harmless
# (uncontended) in a single-instance deployment.

_DEFAULT_TTL_SECONDS = 300

HOLDER = f"{socket.gethostname()}:{os.getpid()}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def try_acquire(source_id: str, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> bool:
    """Attempt to acquire (or reclaim an expired) lock for source_id. Returns
    True if this process now holds it."""
    now = _now()
    expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
    async with async_session_factory() as session:
        try:
            await session.execute(
                text(
                    "INSERT INTO rebuild_lock(source_id, holder, acquired_at, expires_at) "
                    "VALUES (:sid, :holder, :now, :expires)"
                ),
                {
                    "sid": source_id,
                    "holder": HOLDER,
                    "now": now.isoformat(),
                    "expires": expires_at,
                },
            )
            await session.commit()
            return True
        except Exception:
            await session.rollback()

        result = cast(
            CursorResult,
            await session.execute(
                text(
                    "UPDATE rebuild_lock SET holder = :holder, acquired_at = :now, expires_at = :expires "
                    "WHERE source_id = :sid AND expires_at < :now"
                ),
                {
                    "sid": source_id,
                    "holder": HOLDER,
                    "now": now.isoformat(),
                    "expires": expires_at,
                },
            ),
        )
        await session.commit()
        return result.rowcount > 0


async def release(source_id: str) -> None:
    async with async_session_factory() as session:
        await session.execute(
            text(
                "DELETE FROM rebuild_lock WHERE source_id = :sid AND holder = :holder"
            ),
            {"sid": source_id, "holder": HOLDER},
        )
        await session.commit()
