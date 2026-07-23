from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from typing import Any

from ..keywordindex import client as keyword_client
from ..models.source import Source
from ..services import document_formats
from ..services.document_access import (
    flatten_tree,
    get_tree_with_cache,
    read_with_cache,
)
from ..services.document_cache import clear_source
from ..services.document_formats import ExtractedDocument
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


def _hash_content(text_content: str) -> str:
    return hashlib.sha256(text_content.encode("utf-8")).hexdigest()


def _keyword_pages(extracted: ExtractedDocument) -> list[tuple[int | None, str]]:
    """Shape an ExtractedDocument for keyword_client.upsert_document: one
    (page_number, text) row per physical page for a PDF (including blank
    pages, so a document's row count matches its real page count), or a
    single (None, text) row for a document with no page concept."""
    if extracted.pages is None:
        return [(None, extracted.text)]
    return list(enumerate(extracted.pages, start=1))


async def _list_documents(
    source: Source,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Return (documents, tree_warning). The warning is non-None when the tree
    listing itself degraded — e.g. a rate-limited tree fetch that produced an
    empty (or only stale-cached) document list. Callers must surface it rather
    than treating an empty list as "the source has no documents"."""
    tree, warning = await get_tree_with_cache(source)
    docs: list[dict[str, Any]] = []
    if tree and tree.get("root"):
        flatten_tree(tree["root"], docs, source)
    return docs, warning


async def _index_document(
    source: Source,
    path: str,
    sha: str | None = None,
    extracted: ExtractedDocument | None = None,
) -> dict[str, Any] | None:
    """Chunk and embed a single document. Returns a warning dict on per-document
    failure (FR-009), or None on success.

    ``extracted`` may be supplied by a caller that has already downloaded and
    extracted the document (sync_source_index prefetches concurrently),
    avoiding a redundant read; when omitted it is fetched here. A PDF with no
    extractable text anywhere in it surfaces as a document_formats.
    NoExtractableTextError from read_with_cache(), which the broad except
    below turns into exactly this function's normal per-document failure
    path — no special-casing needed for that condition specifically.

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
        if extracted is None:
            extracted, _warning = await read_with_cache(source, path)
        chunks = chunk_markdown(extracted.text)
        if extracted.page_starts is not None:
            for chunk in chunks:
                chunk.page = document_formats.page_for_offset(
                    extracted.page_starts, chunk.char_start
                )
        if not chunks:
            await hash_cache.delete(source.id, path)
            return None
        await hash_cache.mark_in_progress(source.id, path)
        await client.upsert_chunks(source.id, source.name, path, chunks)
        await keyword_client.upsert_document(source.id, path, _keyword_pages(extracted))
        await hash_cache.upsert(source.id, path, _hash_content(extracted.text), sha)
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
) -> tuple[str, str | None, ExtractedDocument | None, dict[str, Any] | None]:
    """Download and extract one document under a concurrency bound. Returns
    (path, sha, extracted, warning); on a fetch/extraction failure (including
    a PDF with no extractable text, FR-007) extracted is None and warning
    describes it (same shape as a per-document index failure)."""
    async with sem:
        try:
            extracted, _warning = await read_with_cache(source, path)
            return path, sha, extracted, None
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
    docs, tree_warning = await _list_documents(source)
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

    # A degraded tree listing (tree_warning) is surfaced to the caller so the
    # source can be flagged instead of silently looking fully indexed.
    warnings: list[dict[str, Any]] = []
    if tree_warning is not None:
        warnings.append(tree_warning)

    for path, sha, extracted, warning in fetched:
        if warning is not None:
            warnings.append(warning)
            continue
        # extracted is only None on a fetch/extraction failure, which is
        # reported via `warning` and handled above, so it is always present
        # here.
        assert extracted is not None
        # A sha-less source can only detect an unchanged document by comparing
        # the freshly fetched content's hash against the last-indexed one.
        if sha is None and known_hashes.get(path) == _hash_content(extracted.text):
            continue
        warning = await _index_document(source, path, sha, extracted=extracted)
        if warning:
            warnings.append(warning)

    # Prune only against a tree we actually listed. When the listing degraded,
    # current_paths is empty (or stale) and can't distinguish a deleted document
    # from one we simply couldn't fetch — pruning then would wipe the whole
    # index on a transient rate limit, so skip it.
    if tree_warning is None:
        for stale_path in (set(known_hashes) | set(known_shas)) - current_paths:
            await remove_document(source, stale_path)

    return warnings


async def delete_source_index(source_id: str) -> None:
    """Purge the vector collection, keyword index, and tree/content cache for a
    deleted source. Each step runs independently: a failure is logged rather
    than raised, so one flaky store does not block the rest or surface an
    HTTP error for a source that is already gone. Anything left behind is
    reconciled later by rebuild_check's startup sweep."""
    for step in (
        lambda: client.delete_collection(source_id),
        lambda: keyword_client.delete_source(source_id),
        lambda: hash_cache.delete_source(source_id),
    ):
        try:
            await step()
        except Exception:
            logger.exception(
                "Cleanup step failed while deleting source %s; continuing "
                "with the remaining cleanup steps",
                source_id,
            )
    clear_source(source_id)


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


def summarize_index_warnings(
    warnings: list[dict[str, Any]],
) -> tuple[str, str | None]:
    """Map the warnings returned by sync_source_index/create_index to a source
    (status, error_message) so partial indexing failures are visible instead of
    the source silently showing 'active'.

    A tree-level warning (no 'path' key) means the document listing itself
    failed, so nothing reliable was indexed — surface it as a hard 'error',
    matching how the poller treats a raised tree fetch. Per-document warnings
    leave a usable-but-incomplete index, reported as 'partial'; the next poll
    re-attempts the missing documents."""
    if not warnings:
        return "active", None
    tree_warnings = [w for w in warnings if "path" not in w]
    if tree_warnings:
        msg = tree_warnings[0].get("message") or "unknown error"
        return "error", f"Failed to list documents: {msg}"
    n = len(warnings)
    return (
        "partial",
        f"{n} document(s) could not be indexed (e.g. rate limit); "
        "will retry on the next sync",
    )
