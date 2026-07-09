from __future__ import annotations

import asyncio
import os

import backend.app.api.sources as sources_module
import pytest
import pytest_asyncio
from backend.app.models.source import Source
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.mark.parametrize("source_type", ["http", "localhost"])
def test_reject_disabled_source_type_raises_422(source_type):
    with pytest.raises(HTTPException) as exc_info:
        sources_module._reject_disabled_source_type(source_type)
    assert exc_info.value.status_code == 422


@pytest.mark.parametrize("source_type", ["local", "github"])
def test_reject_disabled_source_type_allows_active_types(source_type):
    sources_module._reject_disabled_source_type(source_type)  # must not raise


# --- resume_local_sources / _resume_local_source (restart reindex fix) ---

_CREATE_SOURCE_TABLE = """
CREATE TABLE IF NOT EXISTS source (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    polling_interval_seconds INTEGER,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    error_message TEXT
)
"""


@pytest_asyncio.fixture
async def session_factory(monkeypatch, tmp_path):
    db_path = tmp_path / "test.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(text(_CREATE_SOURCE_TABLE))
    monkeypatch.setattr(sources_module, "async_session_factory", factory)
    yield factory
    await engine.dispose()


async def _insert_source(factory, source: Source) -> None:
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO source (id,name,type,path,polling_interval_seconds,created_at,status,error_message)"
                " VALUES (:id,:name,:type,:path,:poll,:created_at,:status,:err)"
            ),
            {**source.to_dict(), "poll": source.polling_interval_seconds, "err": None},
        )
        await session.commit()


async def _get_status(factory, source_id: str) -> str:
    async with factory() as session:
        row = (
            (
                await session.execute(
                    text("SELECT status FROM source WHERE id = :id"), {"id": source_id}
                )
            )
            .mappings()
            .first()
        )
        return row["status"]


@pytest.mark.asyncio
async def test_resume_local_source_restarts_watcher_and_rebuilds_index(
    monkeypatch, session_factory
):
    watched = []
    registered = []
    indexed = []

    monkeypatch.setattr(
        sources_module, "start_watching", lambda sid, path: watched.append((sid, path))
    )
    monkeypatch.setattr(
        sources_module,
        "register_index_listener",
        lambda sid, cb: registered.append(sid),
    )

    async def fake_create_index(source):
        indexed.append(source.id)
        return []

    monkeypatch.setattr(sources_module, "create_index", fake_create_index)

    source = Source(id="s1", name="wiki", type="local", path="~/wiki")
    await _insert_source(session_factory, source)

    await sources_module._resume_local_source(source)

    assert watched == [("s1", os.path.expanduser("~/wiki"))]
    assert registered == ["s1"]
    assert indexed == ["s1"]
    assert await _get_status(session_factory, "s1") == "active"


@pytest.mark.asyncio
async def test_resume_local_source_marks_error_on_index_failure(
    monkeypatch, session_factory
):
    monkeypatch.setattr(sources_module, "start_watching", lambda sid, path: None)
    monkeypatch.setattr(sources_module, "register_index_listener", lambda sid, cb: None)

    async def failing_create_index(source):
        raise RuntimeError("boom")

    monkeypatch.setattr(sources_module, "create_index", failing_create_index)

    source = Source(id="s2", name="vault", type="local", path="~/vault")
    await _insert_source(session_factory, source)

    await sources_module._resume_local_source(source)

    assert await _get_status(session_factory, "s2") == "error"


@pytest.mark.asyncio
async def test_resume_local_sources_only_targets_local_sources(
    monkeypatch, session_factory
):
    resumed = []

    async def fake_resume(source):
        resumed.append(source.id)

    monkeypatch.setattr(sources_module, "_resume_local_source", fake_resume)

    local = Source(id="s3", name="wiki", type="local", path="~/wiki")
    remote = Source(
        id="s4",
        name="repo",
        type="github",
        path="owner/repo",
        polling_interval_seconds=600,
    )
    await _insert_source(session_factory, local)
    await _insert_source(session_factory, remote)

    await sources_module.resume_local_sources()
    await asyncio.sleep(0)  # let the scheduled background tasks run

    assert resumed == ["s3"]
