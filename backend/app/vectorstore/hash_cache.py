from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from ..core.database import async_session_factory


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_known(source_id: str) -> tuple[dict[str, str], dict[str, str]]:
    """Return (content_hash_by_path, blob_sha_by_path) for a source's clean
    (fully-written) rows. Rows still 'in_progress' are excluded — sync_source_index
    must treat them as unknown, not as evidence the document is unchanged."""
    async with async_session_factory() as session:
        rows = await session.execute(
            text(
                "SELECT path, content_hash, blob_sha FROM doc_index_cache "
                "WHERE source_id = :sid AND sync_state = 'clean'"
            ),
            {"sid": source_id},
        )
        hashes: dict[str, str] = {}
        shas: dict[str, str] = {}
        for path, content_hash, blob_sha in rows.all():
            if content_hash is not None:
                hashes[path] = content_hash
            if blob_sha is not None:
                shas[path] = blob_sha
        return hashes, shas


async def mark_in_progress(source_id: str, path: str) -> None:
    """Mark a document's cache row as being (re)written, before its vector-store
    write starts. A row left 'in_progress' at startup means the previous
    process died mid-write."""
    async with async_session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO doc_index_cache(source_id, path, sync_state, updated_at) "
                "VALUES (:sid, :path, 'in_progress', :now) "
                "ON CONFLICT(source_id, path) DO UPDATE SET "
                "sync_state = 'in_progress', updated_at = :now"
            ),
            {"sid": source_id, "path": path, "now": _now()},
        )
        await session.commit()


async def upsert(
    source_id: str,
    path: str,
    content_hash: str | None,
    blob_sha: str | None,
) -> None:
    """Record a document's hash/sha after its vector-store write commits,
    marking the row 'clean' again."""
    async with async_session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO doc_index_cache"
                "(source_id, path, content_hash, blob_sha, sync_state, updated_at) "
                "VALUES (:sid, :path, :hash, :sha, 'clean', :now) "
                "ON CONFLICT(source_id, path) DO UPDATE SET "
                "content_hash = :hash, blob_sha = :sha, sync_state = 'clean', updated_at = :now"
            ),
            {
                "sid": source_id,
                "path": path,
                "hash": content_hash,
                "sha": blob_sha,
                "now": _now(),
            },
        )
        await session.commit()


async def delete(source_id: str, path: str) -> None:
    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM doc_index_cache WHERE source_id = :sid AND path = :path"),
            {"sid": source_id, "path": path},
        )
        await session.commit()


async def delete_source(source_id: str) -> None:
    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM doc_index_cache WHERE source_id = :sid"),
            {"sid": source_id},
        )
        await session.commit()


async def get_in_progress_paths(source_id: str) -> list[str]:
    """Paths whose last write never completed."""
    async with async_session_factory() as session:
        rows = await session.execute(
            text(
                "SELECT path FROM doc_index_cache "
                "WHERE source_id = :sid AND sync_state = 'in_progress'"
            ),
            {"sid": source_id},
        )
        return [row[0] for row in rows.all()]


async def sources_with_in_progress() -> list[str]:
    """Distinct source_ids with at least one row still 'in_progress' — run
    once at startup to find sources whose previous process died mid-write."""
    async with async_session_factory() as session:
        rows = await session.execute(
            text(
                "SELECT DISTINCT source_id FROM doc_index_cache "
                "WHERE sync_state = 'in_progress'"
            )
        )
        return [row[0] for row in rows.all()]


async def count_known(source_id: str) -> int:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM doc_index_cache WHERE source_id = :sid"),
            {"sid": source_id},
        )
        return result.scalar_one()


async def wipe_all() -> int:
    """Invalidate every source's cache (e.g. after an embedding model change
    makes existing vectors incompatible) — the next sync_source_index() call
    for each source then treats every document as new, which is equivalent
    to a full rebuild. Returns the number of rows removed."""
    async with async_session_factory() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM doc_index_cache"))
        count = result.scalar_one()
        await session.execute(text("DELETE FROM doc_index_cache"))
        await session.commit()
        return count
