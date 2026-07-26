from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

import chromadb

from ..core.config import settings
from .chunker import Chunk
from .embedding import MultilingualEmbeddingFunction

logger = logging.getLogger(__name__)

_client: Any = None
_embedding_function: Any = None
_embedding_dimension: int | None = None
_engine_available = False
_init_lock = threading.Lock()

# Bounded retry budget for connecting to the shared vector store at startup:
# a few short attempts, not indefinite and not zero. Aligned with the
# `vectorstore` compose service's own healthcheck timing (docker-compose.yml:
# start_period 10s, interval 30s) rather than an arbitrary number.
_CONNECT_RETRY_ATTEMPTS = 5
_CONNECT_RETRY_DELAY_SECONDS = 3

# Once the startup retries above are exhausted, reconnect_loop() (spawned by
# main.py's lifespan) keeps trying at this more relaxed interval — matching
# `vectorstore`'s own healthcheck interval — so the app recovers on its own
# once the vector store comes back, instead of needing a full backend
# restart to notice.
_RECONNECT_INTERVAL_SECONDS = 30


def _collection_name(source_id: str) -> str:
    return f"src_{source_id}"


def embedding_signature() -> str | None:
    """Identifying signature of the currently configured embedding function
    (class + model name + dimension), used to detect that the embedding
    model changed since the vector store was last written to. Includes the
    model name, not just the class, so two models sharing a wrapper class
    still register as a change. None until init_engine() has run
    successfully at least once."""
    if _embedding_dimension is None:
        return None
    return f"{type(_embedding_function).__name__}:{_embedding_function.name()}:{_embedding_dimension}"


def init_engine() -> bool:
    """Initialize the local embedding engine and vector DB client once, probing
    the embedding function with a trivial call. Distinguishes "engine
    unavailable" from per-document embedding failures, which are handled
    separately by callers. Thread-safe and safe to call multiple times.
    Never raises — a persistent connection failure is reported via the
    return value / is_engine_available(), not an exception, so a
    vector-store outage can never crash the whole backend.

    Both standalone and multi-replica deployments connect to the same
    persistent, shared Chroma server (the `vectorstore` compose service) via
    HttpClient — standalone previously used an in-process EphemeralClient
    that was wiped on every restart, forcing a full re-embed of every
    document each time. Connecting is retried a bounded number of times with
    a short delay in between, so a `vectorstore` container that is merely
    slow to become healthy doesn't need a full backend restart to recover
    from."""
    global _client, _embedding_function, _embedding_dimension, _engine_available
    with _init_lock:
        if _embedding_function is not None:
            return _engine_available
        try:
            _embedding_function = MultilingualEmbeddingFunction()
            vectors = _embedding_function(["healthcheck"])
            _embedding_dimension = len(vectors[0])
        except Exception:
            logger.exception("Failed to initialize the local embedding function")
            _embedding_function = None
            _embedding_dimension = None
            _engine_available = False
            return _engine_available

        for attempt in range(1, _CONNECT_RETRY_ATTEMPTS + 1):
            try:
                _client = chromadb.HttpClient(
                    host=settings.vector_store_host, port=settings.vector_store_port
                )
                _client.heartbeat()
                _engine_available = True
                break
            except Exception:
                _client = None
                if attempt == _CONNECT_RETRY_ATTEMPTS:
                    logger.exception(
                        "Failed to connect to the vector store after %d attempts; "
                        "semantic search will report unavailable until the next "
                        "successful init_engine() call",
                        attempt,
                    )
                    _engine_available = False
                else:
                    logger.warning(
                        "Vector store not reachable yet (attempt %d/%d), retrying in %ds",
                        attempt,
                        _CONNECT_RETRY_ATTEMPTS,
                        _CONNECT_RETRY_DELAY_SECONDS,
                    )
                    time.sleep(_CONNECT_RETRY_DELAY_SECONDS)
    return _engine_available


def is_engine_available() -> bool:
    return _engine_available


def _try_reconnect_once() -> bool:
    """A single, fast connection attempt (no sleep/retry loop of its own) —
    used by reconnect_loop() once init_engine()'s startup retries have been
    exhausted. Returns the resulting availability."""
    global _client, _engine_available
    with _init_lock:
        if _engine_available or _embedding_function is None:
            # Already healthy, or the embedding function itself never
            # initialized (a different failure than a connection issue) —
            # nothing this function can fix.
            return _engine_available
        try:
            _client = chromadb.HttpClient(
                host=settings.vector_store_host, port=settings.vector_store_port
            )
            _client.heartbeat()
            _engine_available = True
            logger.info("Reconnected to the vector store")
        except Exception:
            _client = None
    return _engine_available


async def reconnect_loop() -> None:
    """Background task: while the vector store connection is down, keep
    retrying at a relaxed interval so semantic search recovers on its own
    once the vector store comes back, without requiring a backend restart.
    Exits on its own once reconnected (or if the embedding function itself
    never initialized, in which case retrying the connection can't help)."""
    while not is_engine_available() and _embedding_function is not None:
        await asyncio.sleep(_RECONNECT_INTERVAL_SECONDS)
        await asyncio.to_thread(_try_reconnect_once)


def _require_collection(source_id: str) -> Any:
    if not _engine_available and not init_engine():
        raise RuntimeError("Embedding engine is not available")
    return _client.get_or_create_collection(
        name=_collection_name(source_id), embedding_function=_embedding_function
    )


# --- Blocking vector DB calls. Never call these directly from an async
# context — always go through the async wrappers below via asyncio.to_thread,
# so a slow embed/query/upsert can't stall the shared FastAPI/MCP event loop. ---


def _chunk_metadata(
    source_id: str, source_name: str, path: str, c: Chunk
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "source_id": source_id,
        "source_name": source_name,
        "path": path,
        "chunk_index": c.index,
    }
    # Chroma metadata values must be str/int/float/bool — omit the key
    # entirely for a Markdown chunk (page=None) rather than storing a
    # sentinel; _query_sync reads it back defensively via meta.get("page").
    if c.page is not None:
        meta["page"] = c.page
    return meta


def _upsert_sync(
    source_id: str, source_name: str, path: str, chunks: list[Chunk]
) -> None:
    collection = _require_collection(source_id)
    collection.upsert(
        ids=[f"{source_id}:{path}:{c.index}" for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[_chunk_metadata(source_id, source_name, path, c) for c in chunks],
    )


def _delete_document_sync(source_id: str, path: str) -> None:
    try:
        collection = _require_collection(source_id)
    except RuntimeError:
        return
    collection.delete(where={"$and": [{"source_id": source_id}, {"path": path}]})


def _delete_collection_sync(source_id: str) -> None:
    if _client is None:
        return
    try:
        _client.delete_collection(name=_collection_name(source_id))
    except Exception:
        # Log instead of swallowing — an orphaned collection is reconciled
        # later by the startup orphan sweep, but only if this is visible.
        logger.warning(
            "Failed to delete vector collection for source %s; it may be "
            "left orphaned until the next startup's orphan sweep",
            source_id,
            exc_info=True,
        )


def _list_collection_source_ids_sync() -> list[str]:
    """Returns the source ids that have a vector collection on the connected
    Chroma server. Used by the startup orphan sweep."""
    if _client is None:
        return []
    ids = []
    for collection in _client.list_collections():
        name = collection.name if hasattr(collection, "name") else collection
        if name.startswith("src_"):
            ids.append(name[len("src_") :])
    return ids


def _query_sync(source_id: str, query_text: str, top_k: int) -> list[dict[str, Any]]:
    try:
        collection = _require_collection(source_id)
    except RuntimeError:
        return []
    if collection.count() == 0:
        return []
    result = collection.query(query_texts=[query_text], n_results=top_k)
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    hits: list[dict[str, Any]] = []
    for doc_text, meta, dist in zip(documents, metadatas, distances):
        hits.append(
            {
                "path": meta["path"],
                "source_id": meta["source_id"],
                "source_name": meta["source_name"],
                "chunk_index": meta["chunk_index"],
                "page": meta.get("page"),
                "score": 1.0 / (1.0 + dist),
                "excerpt": doc_text,
            }
        )
    return hits


# --- Public async, vector-DB-agnostic surface used by the rest of the app.
# Swapping the backing store (e.g. to Qdrant) means changing the _sync
# helpers above only; callers never touch chromadb directly. ---


async def upsert_chunks(
    source_id: str, source_name: str, path: str, chunks: list[Chunk]
) -> None:
    await asyncio.to_thread(_upsert_sync, source_id, source_name, path, chunks)


async def delete_document(source_id: str, path: str) -> None:
    await asyncio.to_thread(_delete_document_sync, source_id, path)


async def delete_collection(source_id: str) -> None:
    await asyncio.to_thread(_delete_collection_sync, source_id)


async def list_collection_source_ids() -> list[str]:
    return await asyncio.to_thread(_list_collection_source_ids_sync)


async def query(source_id: str, query_text: str, top_k: int) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_query_sync, source_id, query_text, top_k)
