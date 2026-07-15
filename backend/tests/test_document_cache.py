from __future__ import annotations

import backend.app.services.document_cache as cache_module
import pytest
from backend.app.services.document_cache import (
    clear_source,
    get_cached,
    get_cached_content,
    get_tree_lock,
    mark_stale,
    mark_stale_content,
    set_cached,
    set_cached_content,
)


@pytest.fixture(autouse=True)
def clear_cache():
    cache_module._cache.clear()
    cache_module._content_cache.clear()
    cache_module._locks.clear()
    yield
    cache_module._cache.clear()
    cache_module._content_cache.clear()
    cache_module._locks.clear()


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


# --- Content cache (source_id, path) — FR-004, FR-005: remote sources only ---


def test_set_and_get_content_within_ttl():
    set_cached_content("src-5", "guide/intro.md", "# Intro\n")
    entry = get_cached_content("src-5", "guide/intro.md")
    assert entry is not None
    assert entry["data"] == "# Intro\n"
    assert entry["stale"] is False


def test_get_content_returns_none_after_ttl(monkeypatch):
    set_cached_content("src-6", "a.md", "content")
    monkeypatch.setattr(cache_module, "TTL", 0.0)
    assert get_cached_content("src-6", "a.md") is None


def test_mark_stale_content_keeps_data():
    set_cached_content("src-7", "a.md", "content")
    mark_stale_content("src-7", "a.md")
    entry = get_cached_content("src-7", "a.md")
    assert entry is not None
    assert entry["stale"] is True
    assert entry["data"] == "content"


def test_content_cache_keys_are_scoped_by_path():
    set_cached_content("src-8", "a.md", "content A")
    set_cached_content("src-8", "b.md", "content B")
    assert get_cached_content("src-8", "a.md")["data"] == "content A"
    assert get_cached_content("src-8", "b.md")["data"] == "content B"


def test_get_content_returns_none_for_unknown():
    assert get_cached_content("unknown", "a.md") is None


def test_clear_source_removes_tree_and_content_entries():
    set_cached("src-9", {"root": {}})
    set_cached_content("src-9", "a.md", "content A")
    set_cached_content("src-9", "b.md", "content B")
    set_cached_content("src-other", "a.md", "unrelated")

    clear_source("src-9")

    assert get_cached("src-9") is None
    assert get_cached_content("src-9", "a.md") is None
    assert get_cached_content("src-9", "b.md") is None
    # a different source's content cache must survive
    assert get_cached_content("src-other", "a.md")["data"] == "unrelated"


def test_clear_source_nonexistent_is_noop():
    clear_source("nonexistent")  # should not raise


# --- Per-source tree-fetch lock (single-flight for concurrent tree fetches) ---


def test_get_tree_lock_returns_same_instance_for_same_source():
    assert get_tree_lock("src-10") is get_tree_lock("src-10")


def test_get_tree_lock_returns_different_instance_for_different_source():
    assert get_tree_lock("src-11") is not get_tree_lock("src-12")


def test_clear_source_removes_lock_entry():
    lock = get_tree_lock("src-13")
    clear_source("src-13")
    assert get_tree_lock("src-13") is not lock
