from __future__ import annotations

import asyncio

import backend.app.services.document_access as document_access_module
import backend.app.services.document_cache as cache_module
import pytest
from backend.app.models.source import Source


@pytest.fixture(autouse=True)
def clear_cache():
    cache_module._cache.clear()
    cache_module._locks.clear()
    yield
    cache_module._cache.clear()
    cache_module._locks.clear()


def _make_source(source_id: str) -> Source:
    return Source(
        id=source_id,
        name="test",
        type="gitlab",
        path="https://gitlab.com/group/project",
        polling_interval_seconds=600,
        created_at="2026-01-01T00:00:00+00:00",
        status="syncing",
        error_message=None,
    )


@pytest.mark.asyncio
async def test_concurrent_tree_fetches_coalesce_into_one_upstream_call(monkeypatch):
    """Two callers racing on an uncached source (e.g. the initial indexing
    task and a frontend tree-view request) must trigger build_remote_tree
    only once — the second caller should get the first call's cached result
    instead of independently re-fetching (the bug behind the GitLab
    duplicate-crawl issue)."""
    call_count = 0

    async def slow_build_remote_tree(source):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return {"source_id": source.id, "root": {"is_dir": True, "children": []}}

    monkeypatch.setattr(
        document_access_module, "build_remote_tree", slow_build_remote_tree
    )

    source = _make_source("src-race")
    results = await asyncio.gather(
        document_access_module.get_tree_with_cache(source),
        document_access_module.get_tree_with_cache(source),
    )

    assert call_count == 1
    assert results[0][0] == results[1][0]


@pytest.mark.asyncio
async def test_sequential_calls_after_cache_populated_do_not_refetch(monkeypatch):
    call_count = 0

    async def counting_build_remote_tree(source):
        nonlocal call_count
        call_count += 1
        return {"source_id": source.id, "root": {"is_dir": True, "children": []}}

    monkeypatch.setattr(
        document_access_module, "build_remote_tree", counting_build_remote_tree
    )

    source = _make_source("src-seq")
    await document_access_module.get_tree_with_cache(source)
    await document_access_module.get_tree_with_cache(source)

    assert call_count == 1
