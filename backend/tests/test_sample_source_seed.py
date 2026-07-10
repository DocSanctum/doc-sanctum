from __future__ import annotations

import backend.app.api.sources as sources_module
import backend.app.core.database as database_module
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS source (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    polling_interval_seconds INTEGER,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    error_message TEXT,
    icon TEXT
);
CREATE TABLE IF NOT EXISTS setting (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@pytest_asyncio.fixture
async def session_factory(monkeypatch, tmp_path):
    db_path = tmp_path / "test.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        for stmt in _CREATE_TABLES.strip().split(";"):
            if stmt.strip():
                await conn.execute(text(stmt))
    # get_setting/set_setting live in core.database and read its own module-level
    # async_session_factory, separate from the one sources.py imported by name.
    monkeypatch.setattr(sources_module, "async_session_factory", factory)
    monkeypatch.setattr(database_module, "async_session_factory", factory)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
def sample_docs_dir(tmp_path, monkeypatch):
    docs_dir = tmp_path / "sample-docs"
    docs_dir.mkdir()
    (docs_dir / "RemoveMe.md").write_text("# Sample\n")
    monkeypatch.setattr(sources_module, "_SAMPLE_DOCS_PATH", docs_dir)
    return docs_dir


def _patch_index_and_watch(monkeypatch):
    indexed, watched, registered = [], [], []

    async def fake_create_index(source):
        indexed.append(source.id)
        return []

    monkeypatch.setattr(sources_module, "create_index", fake_create_index)
    monkeypatch.setattr(
        sources_module, "start_watching", lambda sid, path: watched.append((sid, path))
    )
    monkeypatch.setattr(
        sources_module,
        "register_index_listener",
        lambda sid, cb: registered.append(sid),
    )
    return indexed, watched, registered


async def _source_count(factory) -> int:
    async with factory() as session:
        return (await session.execute(text("SELECT COUNT(*) FROM source"))).scalar_one()


@pytest.mark.asyncio
async def test_seed_registers_sample_source_on_empty_db(
    monkeypatch, session_factory, sample_docs_dir
):
    indexed, watched, registered = _patch_index_and_watch(monkeypatch)

    await sources_module.seed_sample_source()

    assert await _source_count(session_factory) == 1
    assert len(indexed) == 1
    assert watched[0][1] == str(sample_docs_dir)
    assert len(registered) == 1
    assert (
        await database_module.get_setting(sources_module._SAMPLE_SOURCE_SEEDED_KEY)
        == "true"
    )


@pytest.mark.asyncio
async def test_seed_is_noop_on_second_call(
    monkeypatch, session_factory, sample_docs_dir
):
    _patch_index_and_watch(monkeypatch)

    await sources_module.seed_sample_source()
    await sources_module.seed_sample_source()

    assert await _source_count(session_factory) == 1


@pytest.mark.asyncio
async def test_seed_skips_when_sources_already_exist(
    monkeypatch, session_factory, sample_docs_dir
):
    indexed, _, _ = _patch_index_and_watch(monkeypatch)
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO source (id,name,type,path,created_at)"
                " VALUES ('s1','existing','local','/tmp/existing','now')"
            )
        )
        await session.commit()

    await sources_module.seed_sample_source()

    assert await _source_count(session_factory) == 1
    assert indexed == []


@pytest.mark.asyncio
async def test_seed_skips_when_sample_docs_dir_missing(
    monkeypatch, session_factory, tmp_path
):
    monkeypatch.setattr(sources_module, "_SAMPLE_DOCS_PATH", tmp_path / "nope")
    indexed, _, _ = _patch_index_and_watch(monkeypatch)

    await sources_module.seed_sample_source()

    assert await _source_count(session_factory) == 0
    assert indexed == []


@pytest.mark.asyncio
async def test_seed_skips_in_scaleout_mode(
    monkeypatch, session_factory, sample_docs_dir
):
    indexed, _, _ = _patch_index_and_watch(monkeypatch)
    monkeypatch.setattr(sources_module.settings, "deployment_mode", "scaleout")

    await sources_module.seed_sample_source()

    assert await _source_count(session_factory) == 0
    assert indexed == []
