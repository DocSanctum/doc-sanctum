from __future__ import annotations

import logging
import time

from sqlalchemy import text

from ..core.database import async_session_factory, get_setting, set_setting
from ..keywordindex.client import KEYWORD_INDEX_SCHEMA_VERSION
from . import chunker, client, hash_cache, rebuild_events, rebuild_lock

logger = logging.getLogger(__name__)

_EMBEDDING_SIGNATURE_KEY = "embedding_model_signature"
_CHUNKING_VERSION_KEY = "chunking_algorithm_version"
_KEYWORD_SCHEMA_VERSION_KEY = "keyword_index_schema_version"

# Sentinel lock rows for the three independent global-mismatch cases below,
# distinct from each other and from the per-source locks used for
# incomplete-write recovery further down — all share the same
# rebuild_lock table. Kept separate (rather than folded into one signature)
# so an operator can tell, from the rebuild event's reason alone, whether an
# embedding-model change, a chunking-algorithm change, or a keyword-index
# schema change caused a given rebuild.
_GLOBAL_LOCK_ID = "__embedding_signature__"
_CHUNKING_LOCK_ID = "__chunking_version__"
_KEYWORD_SCHEMA_LOCK_ID = "__keyword_schema_version__"


async def _source_name(source_id: str) -> str:
    async with async_session_factory() as session:
        row = await session.execute(
            text("SELECT name FROM source WHERE id = :id"), {"id": source_id}
        )
        name = row.scalar_one_or_none()
        return name or source_id


async def _check_embedding_signature() -> None:
    """If the configured embedding model changed since the last run, every
    persisted vector is potentially incompatible — invalidate the entire
    hash cache so every source is fully rebuilt on its next sync, delete
    every existing vector collection (each one's embedding dimension is
    fixed at creation time by Chroma, so leaving a collection created under
    the old model in place would make the next upsert fail once the new
    model's dimension differs), and record one rebuild event describing the
    mismatch."""
    current = client.embedding_signature()
    if current is None:
        return  # engine unavailable; nothing to compare

    stored = await get_setting(_EMBEDDING_SIGNATURE_KEY)
    if stored is None:
        # First time a collection could be created — nothing to invalidate.
        await set_setting(_EMBEDDING_SIGNATURE_KEY, current)
        return
    if stored == current:
        return  # unchanged, no action needed

    if not await rebuild_lock.try_acquire(_GLOBAL_LOCK_ID):
        logger.info(
            "Embedding model signature changed (%s -> %s) but another replica "
            "is already handling the rebuild; skipping",
            stored,
            current,
        )
        return
    try:
        started = time.monotonic()
        invalidated = await hash_cache.wipe_all()
        collection_ids = await client.list_collection_source_ids()
        for source_id in collection_ids:
            await client.delete_collection(source_id)
        await set_setting(_EMBEDDING_SIGNATURE_KEY, current)
        duration = time.monotonic() - started
        rebuild_events.record(
            source_id="*",
            source_name="all sources",
            reason="model-mismatch",
            doc_count=invalidated,
            duration_seconds=duration,
            detail=(
                f"Stored embedding signature '{stored}' no longer matches the "
                f"configured '{current}'. Invalidated {invalidated} cached "
                f"document hash(es) and deleted {len(collection_ids)} vector "
                "collection(s) still configured for the old embedding model "
                "across all sources; each will be fully re-embedded into a "
                "freshly created collection on its next sync."
            ),
        )
        logger.warning(
            "Embedding model signature changed (%s -> %s); invalidated %d "
            "cached document hash(es) and deleted %d vector collection(s), "
            "full rebuild will follow",
            stored,
            current,
            invalidated,
            len(collection_ids),
        )
    finally:
        await rebuild_lock.release(_GLOBAL_LOCK_ID)


async def _check_chunking_version() -> None:
    """If the chunking algorithm changed since the last run (chunker.
    CHUNKING_VERSION bumped), every persisted vector was chunked under the
    old rule — invalidate the entire hash cache so every source is fully
    rebuilt on its next sync, and record one rebuild event describing the
    mismatch. Structurally mirrors _check_embedding_signature() above but
    stays fully independent (own setting key, own lock, own reason) so the
    two conditions are never conflated in the rebuild event log.

    Unlike the embedding-signature check, a missing stored value here does
    NOT mean "nothing has ever been indexed" — this version tracking was
    introduced after the system had already been chunking documents for a
    while, so an existing installation upgrading into this check for the
    first time can easily already have a populated, stale hash cache. The
    stored value is therefore only trusted to mean "nothing to invalidate"
    once wipe_all() itself confirms there was nothing to invalidate."""
    current = str(chunker.CHUNKING_VERSION)

    stored = await get_setting(_CHUNKING_VERSION_KEY)
    if stored == current:
        return  # unchanged, no action needed

    if not await rebuild_lock.try_acquire(_CHUNKING_LOCK_ID):
        logger.info(
            "Chunking algorithm version changed (%s -> %s) but another "
            "replica is already handling the rebuild; skipping",
            stored,
            current,
        )
        return
    try:
        started = time.monotonic()
        invalidated = await hash_cache.wipe_all()
        await set_setting(_CHUNKING_VERSION_KEY, current)
        duration = time.monotonic() - started
        if stored is None and invalidated == 0:
            # A genuinely fresh install: this key has never been set, and
            # there was nothing in the hash cache to invalidate either, so
            # this isn't a real rebuild — just start tracking the version.
            return
        rebuild_events.record(
            source_id="*",
            source_name="all sources",
            reason="chunking-mismatch",
            doc_count=invalidated,
            duration_seconds=duration,
            detail=(
                f"Stored chunking algorithm version "
                f"'{stored if stored is not None else '(none — pre-existing install)'}' "
                f"no longer matches the configured '{current}'. Invalidated "
                f"{invalidated} cached document hash(es) across all "
                "sources; each will be re-chunked and re-embedded on its "
                "next sync."
            ),
        )
        logger.warning(
            "Chunking algorithm version changed (%s -> %s); invalidated %d "
            "cached document hash(es), full rebuild will follow",
            stored,
            current,
            invalidated,
        )
    finally:
        await rebuild_lock.release(_CHUNKING_LOCK_ID)


async def _check_keyword_schema_version() -> None:
    """If the keyword (FTS5) index's row schema changed since the last run
    (keywordindex.client.KEYWORD_INDEX_SCHEMA_VERSION bumped), doc_fts was
    just dropped and recreated by core.database.create_tables() — which
    means every previously indexed document is now missing from keyword
    search until it's re-upserted. Invalidate the entire hash cache so every
    source is fully rebuilt on its next sync (repopulating both the vector
    and keyword stores), and record one rebuild event describing why.
    Structurally mirrors _check_chunking_version() above but stays fully
    independent (own setting key, own lock, own reason).

    Same "missing stored value doesn't necessarily mean fresh install" case
    as _check_chunking_version(): this tracking was introduced after doc_fts
    already existed, so an upgrading install can have a populated hash cache
    with no stored value here yet."""
    current = str(KEYWORD_INDEX_SCHEMA_VERSION)

    stored = await get_setting(_KEYWORD_SCHEMA_VERSION_KEY)
    if stored == current:
        return  # unchanged, no action needed

    if not await rebuild_lock.try_acquire(_KEYWORD_SCHEMA_LOCK_ID):
        logger.info(
            "Keyword index schema version changed (%s -> %s) but another "
            "replica is already handling the rebuild; skipping",
            stored,
            current,
        )
        return
    try:
        started = time.monotonic()
        invalidated = await hash_cache.wipe_all()
        await set_setting(_KEYWORD_SCHEMA_VERSION_KEY, current)
        duration = time.monotonic() - started
        if stored is None and invalidated == 0:
            # A genuinely fresh install: nothing to invalidate, just start
            # tracking the version.
            return
        rebuild_events.record(
            source_id="*",
            source_name="all sources",
            reason="keyword-schema-mismatch",
            doc_count=invalidated,
            duration_seconds=duration,
            detail=(
                f"Stored keyword index schema version "
                f"'{stored if stored is not None else '(none — pre-existing install)'}' "
                f"no longer matches the configured '{current}'. Invalidated "
                f"{invalidated} cached document hash(es) across all "
                "sources; each will be re-indexed (vector and keyword) on "
                "its next sync."
            ),
        )
        logger.warning(
            "Keyword index schema version changed (%s -> %s); invalidated "
            "%d cached document hash(es), full rebuild will follow",
            stored,
            current,
            invalidated,
        )
    finally:
        await rebuild_lock.release(_KEYWORD_SCHEMA_LOCK_ID)


async def _check_incomplete_writes() -> None:
    """A document cache row left 'in_progress' means the previous process
    died mid-write for that source. Invalidate just that source's cache
    (not the whole table) so it gets a full rebuild, and record one rebuild
    event per affected source."""
    source_ids = await hash_cache.sources_with_in_progress()
    for source_id in source_ids:
        if not await rebuild_lock.try_acquire(source_id):
            logger.info(
                "Source %s has an incomplete prior sync but another replica "
                "is already handling its rebuild; skipping",
                source_id,
            )
            continue
        try:
            name = await _source_name(source_id)
            started = time.monotonic()
            invalidated = await hash_cache.count_known(source_id)
            await hash_cache.delete_source(source_id)
            duration = time.monotonic() - started
            rebuild_events.record(
                source_id=source_id,
                source_name=name,
                reason="incomplete-write",
                doc_count=invalidated,
                duration_seconds=duration,
                detail=(
                    "A document write was still marked in-progress at startup, "
                    "meaning the previous process died mid-write. Invalidated "
                    f"{invalidated} cached document hash(es) for this source; "
                    "it will be fully rebuilt on its next sync."
                ),
            )
            logger.warning(
                "Source %s (%s) had an incomplete prior sync; invalidated %d "
                "cached document hash(es), full rebuild will follow",
                source_id,
                name,
                invalidated,
            )
        finally:
            await rebuild_lock.release(source_id)


async def _check_orphaned_collections() -> None:
    """Delete vector collections whose source_id no longer exists in the
    `source` table — left behind when a source's delete_collection call
    failed (see client._delete_collection_sync)."""
    collection_ids = await client.list_collection_source_ids()
    if not collection_ids:
        return
    async with async_session_factory() as session:
        rows = await session.execute(text("SELECT id FROM source"))
        live_ids = {row[0] for row in rows.all()}
    for source_id in collection_ids:
        if source_id in live_ids:
            continue
        await client.delete_collection(source_id)
        rebuild_events.record(
            source_id=source_id,
            source_name=source_id,
            reason="orphaned-collection",
            doc_count=0,
            duration_seconds=0.0,
            detail=(
                "Deleted a vector collection with no matching source row, "
                "left behind by a previous delete that failed partway."
            ),
        )
        logger.warning("Deleted orphaned vector collection for source %s", source_id)


async def check_and_recover() -> None:
    """Run once at startup, after init_engine() and before resume_local_sources()/
    start_polling_all(), so any invalidation below is picked up by the very
    first sync each source performs."""
    await _check_embedding_signature()
    await _check_chunking_version()
    await _check_keyword_schema_version()
    await _check_incomplete_writes()
    await _check_orphaned_collections()
