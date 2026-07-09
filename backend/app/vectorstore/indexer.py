from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

from ..keywordindex import client as keyword_client
from ..mcp.cache import clear_source
from ..mcp.tools.list_documents import _flatten_tree, _get_tree_with_cache
from ..mcp.tools.read_document import read_with_cache
from ..models.source import Source
from . import client
from .chunker import chunk_markdown

logger = logging.getLogger(__name__)

# source_id -> {path: sha256(content)}. Lets sync_source_index (used by the
# remote poller) skip re-embedding documents whose content hasn't changed.
_doc_hashes: dict[str, dict[str, str]] = {}

# source_id -> {path: git blob sha}. GitHub's tree API returns each file's blob
# sha for free alongside the path, so sync_source_index can tell a document is
# unchanged without downloading its content at all (github sources only).
_doc_shas: dict[str, dict[str, str]] = {}


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
    source: Source, path: str, sha: str | None = None
) -> dict[str, Any] | None:
    """Chunk and embed a single document. Returns a warning dict on per-document
    failure (FR-009), or None on success."""
    try:
        content, _warning = await read_with_cache(source, path)
        chunks = chunk_markdown(content)
        if not chunks:
            _doc_hashes.setdefault(source.id, {}).pop(path, None)
            _doc_shas.setdefault(source.id, {}).pop(path, None)
            return None
        await client.upsert_chunks(source.id, source.name, path, chunks)
        await keyword_client.upsert_document(source.id, path, content)
        _doc_hashes.setdefault(source.id, {})[path] = _hash_content(content)
        if sha is not None:
            _doc_shas.setdefault(source.id, {})[path] = sha
        return None
    except Exception as exc:
        logger.warning(
            "Failed to index document %s in source %s: %s", path, source.id, exc
        )
        return {"path": path, "reason": "index_error", "message": str(exc)}


async def remove_document(source: Source, path: str) -> None:
    """Remove all chunks belonging to a single document (edge case: file deleted)."""
    await client.delete_document(source.id, path)
    await keyword_client.delete_document(source.id, path)
    _doc_hashes.get(source.id, {}).pop(path, None)
    _doc_shas.get(source.id, {}).pop(path, None)


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


async def sync_source_index(source: Source) -> list[dict[str, Any]]:
    """Diff the current document list/content against the last known state and
    reindex only added/changed documents, removing deleted ones (FR-010, remote
    sources — called after each poller tree refresh).

    For github sources, each doc carries the git blob sha from the tree API
    response. When it matches the last-indexed sha, the document is skipped
    entirely — no content download happens. Sources without a blob sha (local,
    manifest/http) fall back to fetching content and comparing its hash."""
    docs = await _list_documents(source)
    current_paths = {d["path"] for d in docs}
    known_hashes = _doc_hashes.get(source.id, {})
    known_shas = _doc_shas.get(source.id, {})

    warnings: list[dict[str, Any]] = []
    for doc in docs:
        path = doc["path"]
        sha = doc.get("sha")

        if sha is not None:
            if known_shas.get(path) == sha:
                continue  # unchanged per blob sha -- no need to download at all
        else:
            try:
                content, _warning = await read_with_cache(source, path)
            except Exception as exc:
                warnings.append(
                    {"path": path, "reason": "index_error", "message": str(exc)}
                )
                continue
            if known_hashes.get(path) == _hash_content(content):
                continue

        warning = await _index_document(source, path, sha)
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
    _doc_hashes.pop(source_id, None)
    _doc_shas.pop(source_id, None)


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
