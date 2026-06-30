from __future__ import annotations

import asyncio
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


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


def get_queue(source_id: str) -> asyncio.Queue | None:
    return _queues.get(source_id)
