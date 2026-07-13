from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from typing import Any

from ..keywordindex import client as keyword_client
from ..mcp.cache import clear_source
from ..mcp.tools.list_documents import _flatten_tree, _get_tree_with_cache
from ..mcp.tools.read_document import read_with_cache
from ..models.source import Source
from . import client, hash_cache
from .chunker import chunk_markdown

logger = logging.getLogger(__name__)

# Upper bound on documents fetched from a remote source concurrently during a
# sync. A sync's wall time is dominated by content downloads, not embedding, so
# overlapping the network I/O is the whole win; the bound keeps us clear of
# GitHub/GitLab secondary rate limits that trigger on too many simultaneous
# requests. Embedding and all index/cache writes still happen one at a time.
_FETCH_CONCURRENCY = 10


class EngineUnavailableError(RuntimeError):
    """Raised when the local embedding engine cannot be used at all (FR-014)."""


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def _list_documents(source: Source) -> list[dict[str, Any]]:
    tree, _warning = await _get_tree_with_cache(source)
    docs: list[dict[str, Any]] = []
    if tree and tree.get("root"):
        _flatten_tree(tree["root"], docs, source)
    return docs


async def _index_document(
    source: Source, path: str, sha: str | None = None, content: str | None = None
) -> dict[str, Any] | None:
    """Chunk and embed a single document. Returns a warning dict on per-document
    failure (FR-009), or None on success.

    ``content`` may be supplied by a caller that has already downloaded the
    document (sync_source_index prefetches content concurrently), avoiding a
    redundant read; when omitted the content is fetched here.

    The cache row is marked 'in_progress' before the vector-store write starts
    and 'clean' (via hash_cache.upsert) only after it commits, so a process
    killed mid-write leaves a durable marker that the next startup can use to
    detect the document as needing a rebuild, instead of silently looking
    unchanged next time. An ordinary caught failure here (e.g. the embedding
    engine being temporarily unavailable) is a different situation — the
    process is still alive and this failure is already reported as a
    per-document warning below, so any 'in_progress' marker it left behind
    is cleared rather than left looking like a crash on the next startup."""
    try:
        if content is None:
            content, _warning = await read_with_cache(source, path)
        chunks = chunk_markdown(content)
        if not chunks:
            await hash_cache.delete(source.id, path)
            return None
        await hash_cache.mark_in_progress(source.id, path)
        await client.upsert_chunks(source.id, source.name, path, chunks)
        await keyword_client.upsert_document(source.id, path, content)
        await hash_cache.upsert(source.id, path, _hash_content(content), sha)
        return None
    except Exception as exc:
        logger.warning(
            "Failed to index document %s in source %s: %s", path, source.id, exc
        )
        await hash_cache.delete(source.id, path)
        return {"path": path, "reason": "index_error", "message": str(exc)}


async def remove_document(source: Source, path: str) -> None:
    """Remove all chunks belonging to a single document (edge case: file deleted)."""
    await client.delete_document(source.id, path)
    await keyword_client.delete_document(source.id, path)
    await hash_cache.delete(source.id, path)


async def reindex_document(source: Source, path: str) -> dict[str, Any] | None:
    """Re-chunk and re-embed a single changed document (FR-010, local sources)."""
    await remove_document(source, path)
    return await _index_document(source, path)


async def handle_watch_event(
    source: Source, watch_root: str, payload: dict[str, Any]
) -> None:
    """Translate a raw local filesystem watch event (absolute paths) into a
    targeted reindex/remove call, keyed by the doc path relative to the
    source root (FR-010, local sources)."""
    # watchdog reports symlink-resolved paths (e.g. macOS /tmp -> /private/tmp),
    # so resolve watch_root the same way before computing the relative path.
    real_root = os.path.realpath(watch_root)
    event = payload["event"]
    rel_path = os.path.relpath(os.path.realpath(payload["path"]), real_root)

    if event == "file_deleted":
        await remove_document(source, rel_path)
        return
    if event == "file_renamed":
        old_path = payload.get("old_path")
        if old_path:
            await remove_document(
                source, os.path.relpath(os.path.realpath(old_path), real_root)
            )
        await reindex_document(source, rel_path)
        return
    await reindex_document(source, rel_path)  # file_created / file_modified


async def _prefetch(
    source: Source, path: str, sha: str | None, sem: asyncio.Semaphore
) -> tuple[str, str | None, str | None, dict[str, Any] | None]:
    """Download one document's content under a concurrency bound. Returns
    (path, sha, content, warning); on a fetch failure content is None and
    warning describes it (same shape as a per-document index failure)."""
    async with sem:
        try:
            content, _warning = await read_with_cache(source, path)
            return path, sha, content, None
        except Exception as exc:
            return (
                path,
                sha,
                None,
                {"path": path, "reason": "index_error", "message": str(exc)},
            )


async def sync_source_index(source: Source) -> list[dict[str, Any]]:
    """Diff the current document list/content against the last known state and
    reindex only added/changed documents, removing deleted ones (remote sources
    — called after each poller tree refresh).

    For github sources, each doc carries the git blob sha from the tree API
    response. When it matches the last-indexed sha, the document is skipped
    entirely — no content download happens. Sources without a blob sha (local,
    manifest/http) fall back to fetching content and comparing its hash.

    Content downloads are the dominant cost of a sync, so every candidate
    document (blob-sha-changed, or sha-less and needing a hash comparison) is
    fetched concurrently up to _FETCH_CONCURRENCY. Embedding and the vector /
    keyword / hash-cache writes then run sequentially over the downloaded
    content — the embedding engine is CPU-bound (concurrency buys nothing) and a
    single writer keeps the SQLite-backed caches simple to reason about."""
    docs = await _list_documents(source)
    current_paths = {d["path"] for d in docs}
    known_hashes, known_shas = await hash_cache.get_known(source.id)

    # A blob sha matching the last-indexed one means the document is unchanged;
    # skip it without downloading. Everything else needs its content fetched.
    to_fetch = [
        (doc["path"], doc.get("sha"))
        for doc in docs
        if doc.get("sha") is None or known_shas.get(doc["path"]) != doc.get("sha")
    ]

    sem = asyncio.Semaphore(_FETCH_CONCURRENCY)
    fetched = await asyncio.gather(
        *(_prefetch(source, path, sha, sem) for path, sha in to_fetch)
    )

    warnings: list[dict[str, Any]] = []
    for path, sha, content, warning in fetched:
        if warning is not None:
            warnings.append(warning)
            continue
        # content is only None on a fetch failure, which is reported via
        # `warning` and handled above, so it is always present here.
        assert content is not None
        # A sha-less source can only detect an unchanged document by comparing
        # the freshly fetched content's hash against the last-indexed one.
        if sha is None and known_hashes.get(path) == _hash_content(content):
            continue
        warning = await _index_document(source, path, sha, content=content)
        if warning:
            warnings.append(warning)

    for stale_path in (set(known_hashes) | set(known_shas)) - current_paths:
        await remove_document(source, stale_path)

    return warnings


async def delete_source_index(source_id: str) -> None:
    """Purge the vector collection, keyword index, and tree/content cache for a
    deleted source (FR-012)."""
    await client.delete_collection(source_id)
    await keyword_client.delete_source(source_id)
    clear_source(source_id)
    await hash_cache.delete_source(source_id)


async def create_index(source: Source) -> list[dict[str, Any]]:
    """Synchronously index every document of a newly registered source (FR-011).

    Raises EngineUnavailableError if the embedding engine itself cannot be
    initialized (FR-014) — callers should fail source registration in that case.
    Returns a list of per-document warnings for documents that failed to index
    individually (FR-009); registration still succeeds when this list is non-empty.
    """
    if not client.init_engine():
        raise EngineUnavailableError("Local embedding engine is unavailable")
    return await sync_source_index(source)
