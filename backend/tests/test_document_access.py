from __future__ import annotations

import asyncio
import os

import backend.app.services.document_access as document_access_module
import backend.app.services.document_cache as cache_module
import backend.app.services.watcher as watcher_module
import pytest
from backend.app.models.source import Source

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


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


def _local_source(tmp_path) -> Source:
    return Source(
        id="src-local",
        name="local",
        type="local",
        path=str(tmp_path),
        created_at="2026-01-01T00:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_read_with_cache_extracts_pdf_text_for_local_source(tmp_path):
    with open(os.path.join(FIXTURES, "sample.pdf"), "rb") as f:
        raw = f.read()
    (tmp_path / "sample.pdf").write_bytes(raw)

    extracted, warning = await document_access_module.read_with_cache(
        _local_source(tmp_path), "sample.pdf"
    )

    assert warning is None
    assert "zephyrquartz-page2-marker" in extracted.text
    assert extracted.pages is not None


@pytest.mark.asyncio
async def test_read_raw_with_cache_returns_original_bytes_for_local_source(tmp_path):
    with open(os.path.join(FIXTURES, "sample.pdf"), "rb") as f:
        raw = f.read()
    (tmp_path / "sample.pdf").write_bytes(raw)

    fetched, warning = await document_access_module.read_raw_with_cache(
        _local_source(tmp_path), "sample.pdf"
    )

    assert warning is None
    assert fetched == raw


@pytest.mark.asyncio
async def test_read_with_cache_and_read_raw_with_cache_share_remote_byte_cache(
    monkeypatch,
):
    """Both read_with_cache() (text-extracting) and read_raw_with_cache()
    (bytes-passthrough) must go through the same underlying fetch+cache, so
    reading a remote document's raw bytes and its extracted text doesn't
    double the number of upstream fetches."""
    fetch_count = 0

    async def fake_fetch_remote(source, path):
        nonlocal fetch_count
        fetch_count += 1
        return b"remote markdown content"

    monkeypatch.setattr(document_access_module, "_fetch_remote", fake_fetch_remote)

    source = _make_source("src-shared-cache")
    extracted, _ = await document_access_module.read_with_cache(source, "a.md")
    raw, _ = await document_access_module.read_raw_with_cache(source, "a.md")

    assert extracted.text == "remote markdown content"
    assert raw == b"remote markdown content"
    assert fetch_count == 1


def test_watcher_recognizes_pdf_alongside_markdown(monkeypatch):
    """The local filesystem watcher's per-event filter must accept .pdf
    files the same way it already accepts .md files, and continue to
    reject unsupported extensions."""
    loop = asyncio.new_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    handler = watcher_module._MDHandler("src-watch", loop, queue)

    handler._put("file_created", "/watched/report.pdf")
    handler._put("file_created", "/watched/image.png")

    loop.run_until_complete(asyncio.sleep(0))
    loop.close()

    queued_paths = []
    while not queue.empty():
        queued_paths.append(queue.get_nowait()["path"])
    assert queued_paths == ["/watched/report.pdf"]
