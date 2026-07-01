from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from .chunker import Chunk

logger = logging.getLogger(__name__)

_client: Any = None
_embedding_function: Any = None
_engine_available = False
_init_lock = threading.Lock()


def _collection_name(source_id: str) -> str:
    return f"src_{source_id}"


def init_engine() -> bool:
    """Initialize the local embedding engine and vector DB client once, probing
    the embedding function with a trivial call. Distinguishes "engine
    unavailable" (FR-014) from per-document embedding failures (FR-009).
    Thread-safe and safe to call multiple times."""
    global _client, _embedding_function, _engine_available
    with _init_lock:
        if _embedding_function is not None:
            return _engine_available
        try:
            _embedding_function = DefaultEmbeddingFunction()
            _embedding_function(["healthcheck"])
            _client = chromadb.EphemeralClient()
            _engine_available = True
        except Exception:
            logger.exception("Failed to initialize local embedding engine")
            _embedding_function = None
            _client = None
            _engine_available = False
    return _engine_available


def is_engine_available() -> bool:
    return _engine_available


def _require_collection(source_id: str) -> Any:
    if not _engine_available and not init_engine():
        raise RuntimeError("Embedding engine is not available")
    return _client.get_or_create_collection(
        name=_collection_name(source_id), embedding_function=_embedding_function
    )


# --- Blocking vector DB calls. Never call these directly from an async
# context — always go through the async wrappers below via asyncio.to_thread,
# so a slow embed/query/upsert can't stall the shared FastAPI/MCP event loop. ---


def _upsert_sync(
    source_id: str, source_name: str, path: str, chunks: list[Chunk]
) -> None:
    collection = _require_collection(source_id)
    collection.upsert(
        ids=[f"{source_id}:{path}:{c.index}" for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[
            {
                "source_id": source_id,
                "source_name": source_name,
                "path": path,
                "chunk_index": c.index,
            }
            for c in chunks
        ],
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
        pass


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


async def query(source_id: str, query_text: str, top_k: int) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_query_sync, source_id, query_text, top_k)
