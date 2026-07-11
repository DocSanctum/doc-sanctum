from __future__ import annotations

import asyncio
import json
import os

import backend.app.api.sources as sources_module
import backend.app.core.crypto as crypto
import backend.app.services.poller as poller_module
import httpx
import pytest
import pytest_asyncio
from backend.app.api.sources import PatchSourceRequest, RegisterSourceRequest
from backend.app.mcp.tools import read_document as read_document_module
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
    error_message TEXT,
    icon TEXT,
    access_token_encrypted TEXT
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


# --- Per-source access token (specs/007-source-access-token) ---


@pytest.fixture
def token_key(monkeypatch, tmp_path):
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", tmp_path / "token_key")


@pytest_asyncio.fixture
async def no_op_create_index(monkeypatch):
    async def fake_create_index(source):
        return []

    monkeypatch.setattr(sources_module, "create_index", fake_create_index)


async def _get_access_token_encrypted(factory, source_id: str) -> str | None:
    async with factory() as session:
        row = (
            (
                await session.execute(
                    text("SELECT access_token_encrypted FROM source WHERE id = :id"),
                    {"id": source_id},
                )
            )
            .mappings()
            .first()
        )
        return row["access_token_encrypted"]


@pytest.mark.asyncio
async def test_register_source_with_access_token_stores_encrypted(
    session_factory, no_op_create_index, token_key
):
    req = RegisterSourceRequest(
        type="github",
        path="https://github.com/owner/repo",
        access_token="ghp_secret123",
    )
    async with session_factory() as session:
        result = await sources_module.register_source(req, session)
    await asyncio.sleep(0)  # let _finish_remote_registration's background task run

    assert result["access_token_configured"] is True
    assert "access_token" not in result
    assert "access_token_encrypted" not in result

    stored = await _get_access_token_encrypted(session_factory, result["id"])
    assert stored is not None
    assert stored != "ghp_secret123"  # never stored as plaintext (FR-009)
    assert crypto.decrypt_token(stored) == "ghp_secret123"


@pytest.mark.asyncio
async def test_register_source_without_access_token_leaves_it_unset(
    session_factory, no_op_create_index
):
    req = RegisterSourceRequest(type="github", path="https://github.com/owner/repo2")
    async with session_factory() as session:
        result = await sources_module.register_source(req, session)
    await asyncio.sleep(0)

    assert result["access_token_configured"] is False
    assert await _get_access_token_encrypted(session_factory, result["id"]) is None


@pytest.mark.asyncio
async def test_register_source_ignores_access_token_for_local_type(
    session_factory, no_op_create_index, tmp_path
):
    req = RegisterSourceRequest(
        type="local", path=str(tmp_path), access_token="should-be-ignored"
    )
    async with session_factory() as session:
        result = await sources_module.register_source(req, session)

    assert result["access_token_configured"] is False
    assert await _get_access_token_encrypted(session_factory, result["id"]) is None


@pytest.mark.asyncio
async def test_patch_source_replaces_access_token(
    session_factory, no_op_create_index, token_key
):
    req = RegisterSourceRequest(
        type="github", path="https://github.com/owner/repo3", access_token="orig-token"
    )
    async with session_factory() as session:
        registered = await sources_module.register_source(req, session)
    await asyncio.sleep(0)

    async with session_factory() as session:
        result = await sources_module.patch_source(
            registered["id"],
            PatchSourceRequest(access_token="new-token"),
            session,
        )

    assert result["access_token_configured"] is True
    stored = await _get_access_token_encrypted(session_factory, registered["id"])
    assert crypto.decrypt_token(stored) == "new-token"


@pytest.mark.asyncio
async def test_patch_source_omitting_access_token_keeps_existing(
    session_factory, no_op_create_index, token_key
):
    req = RegisterSourceRequest(
        type="github", path="https://github.com/owner/repo4", access_token="orig-token"
    )
    async with session_factory() as session:
        registered = await sources_module.register_source(req, session)
    await asyncio.sleep(0)

    async with session_factory() as session:
        result = await sources_module.patch_source(
            registered["id"], PatchSourceRequest(name="renamed"), session
        )

    assert result["access_token_configured"] is True
    stored = await _get_access_token_encrypted(session_factory, registered["id"])
    assert crypto.decrypt_token(stored) == "orig-token"


@pytest.mark.asyncio
async def test_patch_source_empty_string_removes_access_token(
    session_factory, no_op_create_index, token_key
):
    req = RegisterSourceRequest(
        type="github", path="https://github.com/owner/repo5", access_token="orig-token"
    )
    async with session_factory() as session:
        registered = await sources_module.register_source(req, session)
    await asyncio.sleep(0)

    async with session_factory() as session:
        result = await sources_module.patch_source(
            registered["id"], PatchSourceRequest(access_token=""), session
        )

    assert result["access_token_configured"] is False
    assert await _get_access_token_encrypted(session_factory, registered["id"]) is None


@pytest.mark.asyncio
async def test_patch_source_ignores_access_token_for_local_type(
    session_factory, no_op_create_index, tmp_path
):
    req = RegisterSourceRequest(type="local", path=str(tmp_path))
    async with session_factory() as session:
        registered = await sources_module.register_source(req, session)

    async with session_factory() as session:
        result = await sources_module.patch_source(
            registered["id"],
            PatchSourceRequest(access_token="should-be-ignored"),
            session,
        )

    assert result["access_token_configured"] is False
    assert await _get_access_token_encrypted(session_factory, registered["id"]) is None


@pytest.mark.asyncio
async def test_list_sources_never_exposes_raw_token_column(
    session_factory, no_op_create_index, token_key
):
    req = RegisterSourceRequest(
        type="github",
        path="https://github.com/owner/repo6",
        access_token="ghp_secret123",
    )
    async with session_factory() as session:
        await sources_module.register_source(req, session)
    await asyncio.sleep(0)

    async with session_factory() as session:
        results = await sources_module.list_sources(session)

    assert len(results) == 1
    assert "access_token_encrypted" not in results[0]
    assert "access_token" not in results[0]
    assert results[0]["access_token_configured"] is True


@pytest.mark.asyncio
async def test_headless_registration_and_mcp_read_document_with_source_token(
    monkeypatch, session_factory, no_op_create_index, token_key
):
    """User Story 3: register a source with a per-source token purely
    through the API (no frontend involved), then read a private document
    through the MCP read_document tool using that same token end to end."""
    monkeypatch.setattr(read_document_module, "async_session_factory", session_factory)

    req = RegisterSourceRequest(
        type="github",
        path="https://github.com/owner/private-repo",
        access_token="ghp_headless123",
    )
    async with session_factory() as session:
        registered = await sources_module.register_source(req, session)
    await asyncio.sleep(0)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("Authorization") == "token ghp_headless123":
            return httpx.Response(200, text="# Private doc\n")
        return httpx.Response(404, json={"message": "Not Found"})

    transport = httpx.MockTransport(handler)
    orig_init = httpx.AsyncClient.__init__

    def patched_init(self, *a, **kw):
        kw["transport"] = transport
        orig_init(self, *a, **kw)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    result = json.loads(
        await read_document_module.read_document_handler(
            registered["id"], "docs/intro.md"
        )
    )

    assert result["content"] == "# Private doc\n"


@pytest.mark.asyncio
async def test_poll_source_sets_error_status_when_private_repo_has_no_token(
    monkeypatch, session_factory
):
    """FR-008 (extended by 007): with neither a source-level token nor the
    global GITHUB_TOKEN configured, polling a private repo must leave the
    source in a clear error state rather than stuck in 'syncing'."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(poller_module, "async_session_factory", session_factory)

    source = Source(
        id="s-notoken",
        name="repo",
        type="github",
        path="https://github.com/owner/private-repo",
        polling_interval_seconds=600,
    )
    await _insert_source(session_factory, source)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    transport = httpx.MockTransport(handler)
    orig_init = httpx.AsyncClient.__init__

    def patched_init(self, *a, **kw):
        kw["transport"] = transport
        orig_init(self, *a, **kw)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    await poller_module._poll_source(source)

    async with session_factory() as session:
        row = (
            (
                await session.execute(
                    text("SELECT status, error_message FROM source WHERE id = :id"),
                    {"id": "s-notoken"},
                )
            )
            .mappings()
            .first()
        )
    assert row["status"] == "error"
    assert row["error_message"]
