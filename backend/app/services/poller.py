from __future__ import annotations
import asyncio
import json
from typing import Any

from ..core.database import async_session_factory
from ..models.source import Source
from sqlalchemy import text
from .github import fetch_github_tree
from .manifest import fetch_manifest_tree
from .watcher import _queues


async def _poll_source(source: Source) -> None:
    try:
        if source.type == "github":
            await fetch_github_tree(source.path, source.id)
        else:
            await fetch_manifest_tree(source.path, source.id, source.name)
        status, error_msg = "active", None
    except Exception as exc:
        status, error_msg = "error", str(exc)

    async with async_session_factory() as session:
        await session.execute(
            text("UPDATE source SET status = :s, error_message = :e WHERE id = :id"),
            {"s": status, "e": error_msg, "id": source.id},
        )
        await session.commit()

    payload: dict[str, Any] = {"event": "tree_refreshed", "source_id": source.id}
    if source.id in _queues:
        await _queues[source.id].put(payload)


async def _run_poller(source: Source) -> None:
    interval = source.polling_interval_seconds or 300
    while True:
        await asyncio.sleep(interval)
        await _poll_source(source)


_tasks: dict[str, asyncio.Task] = {}


async def start_polling_all() -> None:
    async with async_session_factory() as session:
        rows = (await session.execute(
            text("SELECT * FROM source WHERE type != 'local'")
        )).mappings().all()
    for row in rows:
        source = Source.from_row(dict(row))
        if source.id not in _tasks:
            _tasks[source.id] = asyncio.create_task(_run_poller(source))


async def poll_now(source: Source) -> None:
    await _poll_source(source)
    if source.id not in _tasks:
        _tasks[source.id] = asyncio.create_task(_run_poller(source))
