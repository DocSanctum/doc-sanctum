from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

IndexListener = Callable[[dict[str, Any]], Awaitable[None]]

# source_id -> async callback invoked (in addition to the SSE queue) for every
# local .md change, so the vector index stays in sync regardless of whether an
# SSE client is connected (FR-010).
_index_listeners: dict[str, IndexListener] = {}


def register_index_listener(source_id: str, callback: IndexListener) -> None:
    _index_listeners[source_id] = callback


def unregister_index_listener(source_id: str) -> None:
    _index_listeners.pop(source_id, None)


async def _notify_index_listener(payload: dict[str, Any]) -> None:
    listener = _index_listeners.get(payload["source_id"])
    if listener is None:
        return
    try:
        await listener(payload)
    except Exception:
        logger.exception("Index listener failed for source %s", payload["source_id"])


class _MDHandler(FileSystemEventHandler):
    def __init__(
        self, source_id: str, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue
    ):
        self._source_id = source_id
        self._loop = loop
        self._queue = queue

    def _put(self, event_type: str, path: str, old_path: str | None = None) -> None:
        if not path.endswith(".md"):
            return
        payload = {"event": event_type, "source_id": self._source_id, "path": path}
        if old_path:
            payload["old_path"] = old_path
        asyncio.run_coroutine_threadsafe(self._queue.put(payload), self._loop)
        asyncio.run_coroutine_threadsafe(_notify_index_listener(payload), self._loop)

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._put("file_created", str(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._put("file_deleted", str(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._put("file_modified", str(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._put("file_renamed", str(event.dest_path), str(event.src_path))


_observers: dict[str, Any] = {}
_queues: dict[str, asyncio.Queue] = {}


def start_watching(source_id: str, path: str) -> asyncio.Queue:
    if source_id in _observers:
        return _queues[source_id]
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    _queues[source_id] = queue
    handler = _MDHandler(source_id, loop, queue)
    observer = Observer()
    observer.schedule(handler, path, recursive=True)
    observer.start()
    _observers[source_id] = observer
    return queue


def stop_watching(source_id: str) -> None:
    if obs := _observers.pop(source_id, None):
        obs.stop()
        obs.join()
    _queues.pop(source_id, None)
    unregister_index_listener(source_id)


def get_queue(source_id: str) -> asyncio.Queue | None:
    return _queues.get(source_id)
