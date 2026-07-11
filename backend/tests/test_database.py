from __future__ import annotations

import backend.app.core.database as database_module
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.asyncio


@pytest.fixture
def temp_engine(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.sqlite3'}")
    monkeypatch.setattr(database_module, "engine", engine)
    yield engine


async def test_create_tables_creates_doc_fts(temp_engine):
    await database_module.create_tables()

    async with temp_engine.begin() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE name = 'doc_fts'")
        )
        assert result.scalar_one_or_none() == "doc_fts"


async def test_create_tables_is_safe_to_call_again_on_restart(temp_engine):
    """011-keyword-search-fts (US2): create_tables() runs on every backend
    startup (main.py lifespan) — CREATE VIRTUAL TABLE IF NOT EXISTS must not
    error out on an already-initialized database."""
    await database_module.create_tables()
    await database_module.create_tables()  # simulates a second startup

    async with temp_engine.begin() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE name = 'doc_fts'")
        )
        assert result.scalar_one_or_none() == "doc_fts"


async def test_migration_adds_access_token_column_to_pre_existing_sources(temp_engine):
    """007-source-access-token (US2): a source registered before this
    feature shipped has no access_token_encrypted column at all. The
    ALTER TABLE migration must add it as NULL (not error, not require a
    backfill) so the existing row keeps working via the global .env
    fallback (SC-003)."""
    old_schema = """
    CREATE TABLE source (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        path TEXT NOT NULL UNIQUE,
        polling_interval_seconds INTEGER,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        error_message TEXT,
        icon TEXT
    )
    """
    async with temp_engine.begin() as conn:
        await conn.execute(text(old_schema))
        await conn.execute(
            text(
                "INSERT INTO source (id,name,type,path,created_at)"
                " VALUES ('s1','repo','github','https://github.com/o/r','now')"
            )
        )

    await database_module.create_tables()  # runs the migration

    async with temp_engine.begin() as conn:
        columns = {
            row[1]
            for row in (
                await conn.execute(text("PRAGMA table_info(source)"))
            ).fetchall()
        }
        assert "access_token_encrypted" in columns

        row = (
            (
                await conn.execute(
                    text("SELECT access_token_encrypted FROM source WHERE id = 's1'")
                )
            )
            .mappings()
            .first()
        )
        assert row["access_token_encrypted"] is None
