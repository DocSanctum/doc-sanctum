from __future__ import annotations

import logging
import time

from sqlalchemy import text

from ..core.database import async_session_factory, get_setting, set_setting
from . import chunker, client, hash_cache, rebuild_events, rebuild_lock

logger = logging.getLogger(__name__)

_EMBEDDING_SIGNATURE_KEY = "embedding_model_signature"
_CHUNKING_VERSION_KEY = "chunking_algorithm_version"

# Sentinel lock rows for the two independent global-mismatch cases below,
# distinct from each other and from the per-source locks used for
# incomplete-write recovery further down — all share the same
# rebuild_lock table. Kept separate (rather than folded into one signature)
# so an operator can tell, from the rebuild event's reason alone, whether an
# embedding-model change or a chunking-algorithm change caused a given
# rebuild.
_GLOBAL_LOCK_ID = "__embedding_signature__"
_CHUNKING_LOCK_ID = "__chunking_version__"


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
    hash cache so every source is fully rebuilt on its next sync, and
    record one rebuild event describing the mismatch."""
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
                "document hash(es) across all sources; each will be "
                "re-embedded on its next sync."
            ),
        )
        logger.warning(
            "Embedding model signature changed (%s -> %s); invalidated %d "
            "cached document hash(es), full rebuild will follow",
            stored,
            current,
            invalidated,
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


async def check_and_recover() -> None:
    """Run once at startup, after init_engine() and before resume_local_sources()/
    start_polling_all(), so any invalidation below is picked up by the very
    first sync each source performs."""
    await _check_embedding_signature()
    await _check_chunking_version()
    await _check_incomplete_writes()
