import time
from typing import Any

TTL = 60.0

_cache: dict[str, dict[str, Any]] = {}


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
