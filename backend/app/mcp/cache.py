import asyncio
import time
from typing import Any

TTL = 60.0

_cache: dict[str, dict[str, Any]] = {}
_content_cache: dict[str, dict[str, Any]] = {}
_locks: dict[str, asyncio.Lock] = {}


def get_tree_lock(source_id: str) -> asyncio.Lock:
    """Per-source lock so concurrent tree-fetch callers (e.g. the initial
    indexing task and a frontend tree-view request racing right after
    registration) coalesce into a single upstream fetch instead of each
    independently re-walking a slow paginated API (e.g. GitLab's tree
    endpoint for a large repo)."""
    return _locks.setdefault(source_id, asyncio.Lock())


def get_cached(source_id: str) -> dict[str, Any] | None:
    entry = _cache.get(source_id)
    if entry is None:
        return None
    if not entry["stale"] and (time.monotonic() - entry["fetched_at"]) > TTL:
        return None
    return entry


def set_cached(source_id: str, data: dict[str, Any]) -> None:
    _cache[source_id] = {
        "data": data,
        "fetched_at": time.monotonic(),
        "stale": False,
    }


def mark_stale(source_id: str) -> None:
    if source_id in _cache:
        _cache[source_id]["stale"] = True


def _content_key(source_id: str, path: str) -> str:
    return f"{source_id}:{path}"


def get_cached_content(source_id: str, path: str) -> dict[str, Any] | None:
    entry = _content_cache.get(_content_key(source_id, path))
    if entry is None:
        return None
    if not entry["stale"] and (time.monotonic() - entry["fetched_at"]) > TTL:
        return None
    return entry


def set_cached_content(source_id: str, path: str, content: str) -> None:
    _content_cache[_content_key(source_id, path)] = {
        "data": content,
        "fetched_at": time.monotonic(),
        "stale": False,
    }


def mark_stale_content(source_id: str, path: str) -> None:
    key = _content_key(source_id, path)
    if key in _content_cache:
        _content_cache[key]["stale"] = True


def clear_source(source_id: str) -> None:
    """Remove all tree and content cache entries for a deleted source (FR-012)."""
    _cache.pop(source_id, None)
    _locks.pop(source_id, None)
    prefix = f"{source_id}:"
    for key in [k for k in _content_cache if k.startswith(prefix)]:
        _content_cache.pop(key, None)
