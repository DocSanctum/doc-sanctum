from __future__ import annotations

import backend.app.core.database as database_module
import backend.app.keywordindex.client as keywordindex_module
import backend.app.vectorstore.chunker as chunker_module
import backend.app.vectorstore.client as client_module
import backend.app.vectorstore.hash_cache as hash_cache_module
import backend.app.vectorstore.indexer as indexer_module
import backend.app.vectorstore.rebuild_check as rebuild_check_module
import backend.app.vectorstore.rebuild_events as rebuild_events_module
import backend.app.vectorstore.rebuild_lock as rebuild_lock_module
import pytest
import pytest_asyncio
from backend.app.models.source import Source
from backend.app.services.document_formats import ExtractedDocument
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.asyncio

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS source (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE, polling_interval_seconds INTEGER,
    created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
    error_message TEXT, icon TEXT
);
CREATE TABLE IF NOT EXISTS setting (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS doc_index_cache (
    source_id TEXT NOT NULL, path TEXT NOT NULL, content_hash TEXT, blob_sha TEXT,
    sync_state TEXT NOT NULL DEFAULT 'clean', updated_at TEXT NOT NULL,
    PRIMARY KEY (source_id, path)
);
CREATE TABLE IF NOT EXISTS rebuild_lock (
    source_id TEXT PRIMARY KEY, holder TEXT NOT NULL,
    acquired_at TEXT NOT NULL, expires_at TEXT NOT NULL
);
"""


@pytest_asyncio.fixture
async def db(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.sqlite3'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        for stmt in _CREATE_TABLES.strip().split(";"):
            if stmt.strip():
                await conn.execute(text(stmt))
    for mod in (hash_cache_module, rebuild_lock_module, rebuild_check_module):
        monkeypatch.setattr(mod, "async_session_factory", factory)
    # rebuild_check calls get_setting/set_setting, which open their own
    # sessions via the database module's factory directly.
    monkeypatch.setattr(database_module, "async_session_factory", factory)
    yield factory
    await engine.dispose()


async def _insert_source(factory, source: Source) -> None:
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO source (id,name,type,path,polling_interval_seconds,"
                "created_at,status,error_message,icon) VALUES "
                "(:id,:name,:type,:path,:poll,:created_at,:status,:err,:icon)"
            ),
            {
                **source.to_dict(),
                "poll": source.polling_interval_seconds,
                "err": None,
            },
        )
        await session.commit()


# --- hash_cache: durable replacement for the old in-process dicts ---


async def test_upsert_then_get_known_round_trips(db):
    await hash_cache_module.upsert("s1", "a.md", "hash-a", None)
    await hash_cache_module.upsert("s1", "b.md", None, "sha-b")

    hashes, shas = await hash_cache_module.get_known("s1")
    assert hashes == {"a.md": "hash-a"}
    assert shas == {"b.md": "sha-b"}


async def test_in_progress_row_excluded_from_known(db):
    """A row left 'in_progress' (simulated crash mid-write) must not look
    like a known-unchanged document."""
    await hash_cache_module.mark_in_progress("s1", "a.md")

    hashes, shas = await hash_cache_module.get_known("s1")
    assert hashes == {}
    assert shas == {}
    assert await hash_cache_module.sources_with_in_progress() == ["s1"]


async def test_wipe_all_invalidates_every_source(db):
    await hash_cache_module.upsert("s1", "a.md", "h1", None)
    await hash_cache_module.upsert("s2", "b.md", "h2", None)

    removed = await hash_cache_module.wipe_all()

    assert removed == 2
    hashes, _ = await hash_cache_module.get_known("s1")
    assert hashes == {}


# --- sync_source_index: unchanged docs aren't re-embedded, changed/added/
# removed docs are handled correctly, backed by the durable hash_cache
# instead of an in-process dict ---


@pytest_asyncio.fixture
async def fake_vector_writes(monkeypatch):
    calls = {"upsert": [], "delete": []}

    async def fake_upsert_chunks(source_id, source_name, path, chunks):
        calls["upsert"].append(path)

    async def fake_delete_document(source_id, path):
        calls["delete"].append(path)

    async def fake_noop(*args, **kwargs):
        return None

    monkeypatch.setattr(indexer_module.client, "upsert_chunks", fake_upsert_chunks)
    monkeypatch.setattr(indexer_module.client, "delete_document", fake_delete_document)
    monkeypatch.setattr(indexer_module.keyword_client, "upsert_document", fake_noop)
    monkeypatch.setattr(indexer_module.keyword_client, "delete_document", fake_noop)
    return calls


def _docs(paths_and_content: dict[str, str]):
    return [{"path": p} for p in paths_and_content]


async def test_unchanged_source_reembeds_nothing_on_second_sync(
    db, fake_vector_writes, monkeypatch
):
    source = Source(name="s", type="local", path="/tmp/s")
    content_by_path = {"a.md": "# A\n\nhello world"}

    async def fake_list_documents(_source):
        return _docs(content_by_path), None

    async def fake_read_with_cache(_source, path):
        return ExtractedDocument(
            text=content_by_path[path], pages=None, page_starts=None
        ), None

    monkeypatch.setattr(indexer_module, "_list_documents", fake_list_documents)
    monkeypatch.setattr(indexer_module, "read_with_cache", fake_read_with_cache)

    await indexer_module.sync_source_index(source)
    assert fake_vector_writes["upsert"] == ["a.md"]

    # Simulate a backend restart: nothing else changes, cache persists in db.
    fake_vector_writes["upsert"].clear()
    await indexer_module.sync_source_index(source)
    assert (
        fake_vector_writes["upsert"] == []
    )  # zero re-embeds for an unchanged document


async def test_partial_change_reembeds_only_changed_doc_and_prunes_deleted(
    db, fake_vector_writes, monkeypatch
):
    source = Source(name="s", type="local", path="/tmp/s")
    content_by_path = {"a.md": "content a", "b.md": "content b"}

    async def fake_list_documents(_source):
        return _docs(content_by_path), None

    async def fake_read_with_cache(_source, path):
        return ExtractedDocument(
            text=content_by_path[path], pages=None, page_starts=None
        ), None

    monkeypatch.setattr(indexer_module, "_list_documents", fake_list_documents)
    monkeypatch.setattr(indexer_module, "read_with_cache", fake_read_with_cache)

    await indexer_module.sync_source_index(source)
    fake_vector_writes["upsert"].clear()

    # b.md changes, a.md is removed from the source entirely.
    content_by_path["b.md"] = "content b v2"
    del content_by_path["a.md"]

    await indexer_module.sync_source_index(source)

    assert fake_vector_writes["upsert"] == [
        "b.md"
    ]  # only the changed document is re-embedded
    assert fake_vector_writes["delete"] == ["a.md"]  # the removed document is pruned


# --- rebuild_check: model mismatch / incomplete write recovery ---


async def test_first_run_stores_signature_without_rebuild_event(
    db, monkeypatch, tmp_path
):
    monkeypatch.setattr(client_module, "_embedding_dimension", 384)
    monkeypatch.setattr(client_module, "_embedding_function", object())

    events_dir = tmp_path / "events"
    monkeypatch.setattr(rebuild_events_module, "_EVENTS_DIR", events_dir)

    await rebuild_check_module._check_embedding_signature()

    assert not events_dir.exists() or not list(events_dir.iterdir())


async def test_signature_mismatch_invalidates_cache_and_writes_event(
    db, monkeypatch, tmp_path
):
    from backend.app.core.database import set_setting

    await set_setting("embedding_model_signature", "OldFn:128")
    await hash_cache_module.upsert("s1", "a.md", "h1", None)

    monkeypatch.setattr(client_module, "_embedding_dimension", 384)

    class _Fn:
        pass

    monkeypatch.setattr(client_module, "_embedding_function", _Fn())

    events_dir = tmp_path / "events"
    monkeypatch.setattr(rebuild_events_module, "_EVENTS_DIR", events_dir)

    await rebuild_check_module._check_embedding_signature()

    hashes, _ = await hash_cache_module.get_known("s1")
    assert hashes == {}  # cache invalidated -> next sync fully rebuilds

    files = list(events_dir.iterdir())
    assert len(files) == 1
    first_line = files[0].read_text().splitlines()[0]
    assert first_line.startswith("REBUILT source=all sources reason=model-mismatch")


async def test_chunking_version_mismatch_invalidates_cache_and_writes_distinct_event(
    db, monkeypatch, tmp_path
):
    """A chunking-algorithm-version mismatch must invalidate the hash cache
    the same way an embedding-model mismatch does, but be recorded under a
    *distinct* reason so an operator can tell the two apart without
    cross-referencing other logs."""
    from backend.app.core.database import set_setting

    await set_setting(
        "chunking_algorithm_version", "1"
    )  # stale: real value is CHUNKING_VERSION
    await hash_cache_module.upsert("s1", "a.md", "h1", None)

    events_dir = tmp_path / "events"
    monkeypatch.setattr(rebuild_events_module, "_EVENTS_DIR", events_dir)

    await rebuild_check_module._check_chunking_version()

    hashes, _ = await hash_cache_module.get_known("s1")
    assert hashes == {}  # cache invalidated -> next sync fully re-chunks

    files = list(events_dir.iterdir())
    assert len(files) == 1
    first_line = files[0].read_text().splitlines()[0]
    assert first_line.startswith("REBUILT source=all sources reason=chunking-mismatch")
    # distinct from the embedding-model-mismatch reason asserted above
    assert "reason=model-mismatch" not in first_line


async def test_chunking_version_first_run_stores_value_without_rebuild_event(
    db, monkeypatch, tmp_path
):
    """A genuinely fresh install (no stored version, nothing in the hash
    cache either) just starts tracking the version — no rebuild event,
    since there's nothing to rebuild."""
    events_dir = tmp_path / "events"
    monkeypatch.setattr(rebuild_events_module, "_EVENTS_DIR", events_dir)

    await rebuild_check_module._check_chunking_version()

    assert not events_dir.exists() or not list(events_dir.iterdir())

    from backend.app.core.database import get_setting

    stored = await get_setting("chunking_algorithm_version")
    assert stored == str(chunker_module.CHUNKING_VERSION)


async def test_chunking_version_first_observation_with_existing_data_still_rebuilds(
    db, monkeypatch, tmp_path
):
    """An installation upgrading into this check for the first time can
    already have documents indexed under the old, untracked chunking rule
    — a missing stored version must NOT be treated as "nothing to
    invalidate" in that case. This is the exact scenario that occurs the
    first time an existing deployment restarts after gaining this check."""
    await hash_cache_module.upsert("s1", "a.md", "h1", None)

    events_dir = tmp_path / "events"
    monkeypatch.setattr(rebuild_events_module, "_EVENTS_DIR", events_dir)

    await rebuild_check_module._check_chunking_version()

    hashes, _ = await hash_cache_module.get_known("s1")
    assert hashes == {}  # cache invalidated -> next sync fully re-chunks

    files = list(events_dir.iterdir())
    assert len(files) == 1
    first_line = files[0].read_text().splitlines()[0]
    assert first_line.startswith("REBUILT source=all sources reason=chunking-mismatch")

    from backend.app.core.database import get_setting

    stored = await get_setting("chunking_algorithm_version")
    assert stored == str(chunker_module.CHUNKING_VERSION)


async def test_incomplete_write_invalidates_only_that_source(db, monkeypatch, tmp_path):
    source = Source(name="Crashed Source", type="local", path="/tmp/crashed")
    await _insert_source(db, source)
    source_id = source.id

    await hash_cache_module.upsert(source_id, "a.md", "h1", None)
    await hash_cache_module.mark_in_progress(source_id, "b.md")
    await hash_cache_module.upsert("other-source", "c.md", "h2", None)

    events_dir = tmp_path / "events"
    monkeypatch.setattr(rebuild_events_module, "_EVENTS_DIR", events_dir)

    await rebuild_check_module._check_incomplete_writes()

    hashes, _ = await hash_cache_module.get_known(source_id)
    assert hashes == {}  # crashed source's cache fully invalidated

    other_hashes, _ = await hash_cache_module.get_known("other-source")
    assert other_hashes == {"c.md": "h2"}  # unaffected source untouched

    files = list(events_dir.iterdir())
    assert len(files) == 1
    first_line = files[0].read_text().splitlines()[0]
    assert "reason=incomplete-write" in first_line
    assert "Crashed Source" in files[0].name or "Crashed-Source" in files[0].name


async def test_orphaned_collection_is_deleted_and_live_one_is_kept(
    db, monkeypatch, tmp_path
):
    """A vector collection with no matching source row (left behind by a
    previous delete_collection call that failed) must be deleted on the next
    startup sweep. A collection whose source row still exists must be left
    alone."""
    source = Source(name="Live Source", type="local", path="/tmp/live")
    await _insert_source(db, source)

    async def fake_list_collection_source_ids():
        return [source.id, "orphaned-id"]

    deleted: list[str] = []

    async def fake_delete_collection(source_id):
        deleted.append(source_id)

    monkeypatch.setattr(
        client_module, "list_collection_source_ids", fake_list_collection_source_ids
    )
    monkeypatch.setattr(client_module, "delete_collection", fake_delete_collection)

    events_dir = tmp_path / "events"
    monkeypatch.setattr(rebuild_events_module, "_EVENTS_DIR", events_dir)

    await rebuild_check_module._check_orphaned_collections()

    assert deleted == ["orphaned-id"]  # live source's collection untouched

    files = list(events_dir.iterdir())
    assert len(files) == 1
    first_line = files[0].read_text().splitlines()[0]
    assert "reason=orphaned-collection" in first_line
    assert "orphaned-id" in first_line


async def test_no_orphaned_collections_writes_no_event(db, monkeypatch, tmp_path):
    async def fake_list_collection_source_ids():
        return []

    monkeypatch.setattr(
        client_module, "list_collection_source_ids", fake_list_collection_source_ids
    )

    events_dir = tmp_path / "events"
    monkeypatch.setattr(rebuild_events_module, "_EVENTS_DIR", events_dir)

    await rebuild_check_module._check_orphaned_collections()

    assert not events_dir.exists() or not list(events_dir.iterdir())


# --- rebuild_lock: cross-replica coordination ---


async def test_second_acquire_fails_while_lock_held(db):
    assert await rebuild_lock_module.try_acquire("s1", ttl_seconds=300) is True
    assert await rebuild_lock_module.try_acquire("s1", ttl_seconds=300) is False


async def test_acquire_succeeds_after_release(db):
    assert await rebuild_lock_module.try_acquire("s1") is True
    await rebuild_lock_module.release("s1")
    assert await rebuild_lock_module.try_acquire("s1") is True


async def test_acquire_succeeds_after_expiry(db):
    assert await rebuild_lock_module.try_acquire("s1", ttl_seconds=0) is True
    # ttl_seconds=0 means expires_at is already in the past by the time the
    # next attempt runs, so a different holder can reclaim it.
    assert await rebuild_lock_module.try_acquire("s1", ttl_seconds=300) is True


# --- _check_keyword_schema_version (014-pdf-parser-support): FTS5 tables
# can't be ALTERed in place, so doc_fts is dropped and recreated when its
# schema changes (core/database.py) -- this check is what forces a full
# reindex afterwards, mirroring _check_chunking_version's pattern. ---


async def test_keyword_schema_version_mismatch_invalidates_cache_and_writes_distinct_event(
    db, monkeypatch, tmp_path
):
    """A keyword-index-schema-version mismatch (doc_fts was just recreated
    by create_tables()) must invalidate the hash cache so previously
    indexed documents get re-upserted into the now-empty doc_fts, recorded
    under its own reason distinct from model-mismatch/chunking-mismatch."""
    from backend.app.core.database import set_setting

    await set_setting(
        "keyword_index_schema_version", "0"
    )  # stale: real value is KEYWORD_INDEX_SCHEMA_VERSION
    await hash_cache_module.upsert("s1", "a.md", "h1", None)

    events_dir = tmp_path / "events"
    monkeypatch.setattr(rebuild_events_module, "_EVENTS_DIR", events_dir)

    await rebuild_check_module._check_keyword_schema_version()

    hashes, _ = await hash_cache_module.get_known("s1")
    assert hashes == {}  # cache invalidated -> next sync fully re-indexes

    files = list(events_dir.iterdir())
    assert len(files) == 1
    first_line = files[0].read_text().splitlines()[0]
    assert first_line.startswith(
        "REBUILT source=all sources reason=keyword-schema-mismatch"
    )
    assert "reason=model-mismatch" not in first_line
    assert "reason=chunking-mismatch" not in first_line


async def test_keyword_schema_version_first_run_stores_value_without_rebuild_event(
    db, monkeypatch, tmp_path
):
    """A genuinely fresh install just starts tracking the version — no
    rebuild event, since there's nothing in the hash cache to invalidate."""
    events_dir = tmp_path / "events"
    monkeypatch.setattr(rebuild_events_module, "_EVENTS_DIR", events_dir)

    await rebuild_check_module._check_keyword_schema_version()

    assert not events_dir.exists() or not list(events_dir.iterdir())

    from backend.app.core.database import get_setting

    stored = await get_setting("keyword_index_schema_version")
    assert stored == str(keywordindex_module.KEYWORD_INDEX_SCHEMA_VERSION)


async def test_keyword_schema_version_first_observation_with_existing_data_still_rebuilds(
    db, monkeypatch, tmp_path
):
    """An installation upgrading into this check for the first time (doc_fts
    just got recreated without a page column previously existing) can
    already have documents indexed — a missing stored version must NOT be
    treated as "nothing to invalidate" in that case."""
    await hash_cache_module.upsert("s1", "a.md", "h1", None)

    events_dir = tmp_path / "events"
    monkeypatch.setattr(rebuild_events_module, "_EVENTS_DIR", events_dir)

    await rebuild_check_module._check_keyword_schema_version()

    hashes, _ = await hash_cache_module.get_known("s1")
    assert hashes == {}

    files = list(events_dir.iterdir())
    assert len(files) == 1
    first_line = files[0].read_text().splitlines()[0]
    assert first_line.startswith(
        "REBUILT source=all sources reason=keyword-schema-mismatch"
    )
