from __future__ import annotations

import asyncio
import contextlib
import logging

from sqlalchemy import text

from ..core.database import async_session_factory
from ..models.source import Source
from ..vectorstore.indexer import summarize_index_warnings, sync_source_index
from .document_cache import get_tree_lock, set_cached
from .github import fetch_github_tree
from .gitlab import fetch_gitlab_tree
from .manifest import fetch_manifest_tree
from .token_resolver import resolve_access_token
from .watcher import _queues

logger = logging.getLogger(__name__)


async def _write_status(source_id: str, status: str, error_msg: str | None) -> None:
    async with async_session_factory() as session:
        await session.execute(
            text("UPDATE source SET status = :s, error_message = :e WHERE id = :id"),
            {"s": status, "e": error_msg, "id": source_id},
        )
        await session.commit()


async def _poll_source(source: Source) -> None:
    def notify() -> None:
        if source.id in _queues:
            _queues[source.id].put_nowait(
                {"event": "tree_refreshed", "source_id": source.id}
            )

    try:
        # Shares the lock with on-demand /tree requests (see
        # document_cache.get_tree_lock) so a periodic poll and a manual tree
        # fetch can't both independently re-walk a slow paginated remote
        # API (e.g. GitLab's tree endpoint for a large repo) at once.
        async with get_tree_lock(source.id):
            if source.type == "github":
                tree = await fetch_github_tree(
                    source.path, source.id, resolve_access_token(source)
                )
            elif source.type == "gitlab":
                tree = await fetch_gitlab_tree(
                    source.path, source.id, resolve_access_token(source)
                )
            else:
                tree = await fetch_manifest_tree(source.path, source.id, source.name)
            set_cached(source.id, tree)
    except Exception as exc:
        await _write_status(source.id, "error", str(exc))
        notify()
        return

    # The tree listed successfully; the final status reflects the index sync so
    # that per-document fetch failures downgrade the source to "partial" instead
    # of it silently staying "active" while missing documents.
    try:
        warnings = await sync_source_index(source)
        status, error_msg = summarize_index_warnings(warnings)
    except Exception:
        logger.exception("Failed to sync vector index for source %s", source.id)
        status, error_msg = "error", "Failed to sync the document index"

    await _write_status(source.id, status, error_msg)
    notify()


async def _run_poller(source: Source) -> None:
    # Polls immediately on the first iteration (rather than sleeping first)
    # so a backend restart picks up any changes right away instead of
    # waiting up to a full poll interval. The vector index and its
    # change-tracking cache now persist across restarts, so this first
    # sync_source_index() call is a fast no-op diff when nothing changed,
    # not a full rebuild.
    interval = source.polling_interval_seconds or 300
    while True:
        await _poll_source(source)
        await asyncio.sleep(interval)


_tasks: dict[str, asyncio.Task] = {}


async def start_polling_all() -> None:
    async with async_session_factory() as session:
        rows = (
            (await session.execute(text("SELECT * FROM source WHERE type != 'local'")))
            .mappings()
            .all()
        )
    for row in rows:
        source = Source.from_row(dict(row))
        if source.id not in _tasks:
            _tasks[source.id] = asyncio.create_task(_run_poller(source))


async def poll_now(source: Source) -> None:
    await _poll_source(source)
    if source.id not in _tasks:
        _tasks[source.id] = asyncio.create_task(_run_poller(source))


async def stop_polling(source_id: str) -> None:
    """Cancel and await a source's recurring poll loop, so a deleted source's
    background poller cannot outlive it and keep recreating its vector
    collection every interval (see delete_source in api/sources.py). Without
    this, nothing ever stopped `_run_poller` — it ran forever, since neither
    `_tasks` nor its task was ever cleared on delete."""
    task = _tasks.pop(source_id, None)
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
