from __future__ import annotations

import backend.app.mcp.cache as cache_module
import pytest
from backend.app.mcp.cache import get_cached, mark_stale, set_cached


@pytest.fixture(autouse=True)
def clear_cache():
    cache_module._cache.clear()
    yield
    cache_module._cache.clear()


def test_set_and_get_within_ttl():
    set_cached("src-1", {"root": {}})
    entry = get_cached("src-1")
    assert entry is not None
    assert entry["data"] == {"root": {}}
    assert entry["stale"] is False


def test_get_returns_none_after_ttl(monkeypatch):
    set_cached("src-2", {"root": {}})
    monkeypatch.setattr(cache_module, "TTL", 0.0)
    # After TTL=0, non-stale entry should expire
    entry = get_cached("src-2")
    assert entry is None


def test_mark_stale_keeps_data():
    set_cached("src-3", {"root": {"children": []}})
    mark_stale("src-3")
    entry = get_cached("src-3")
    assert entry is not None
    assert entry["stale"] is True
    assert entry["data"] == {"root": {"children": []}}


def test_mark_stale_nonexistent_is_noop():
    mark_stale("nonexistent")  # should not raise


def test_get_returns_none_for_unknown():
    assert get_cached("unknown") is None


def test_stale_entry_returned_even_after_ttl(monkeypatch):
    set_cached("src-4", {"root": {}})
    mark_stale("src-4")
    monkeypatch.setattr(cache_module, "TTL", 0.0)
    # Stale entries bypass TTL check and are always returned
    entry = get_cached("src-4")
    assert entry is not None
    assert entry["stale"] is True
