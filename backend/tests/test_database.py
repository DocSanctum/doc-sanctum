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


async def test_create_tables_adds_page_column_to_pre_existing_doc_fts(temp_engine):
    """014-pdf-parser-support: a doc_fts table created before PDF support
    shipped has no `page` column, and FTS5 tables can't be ALTERed in place
    (research.md §4) — create_tables() must detect this and drop+recreate
    the table with the column added, without erroring."""
    old_schema = """
    CREATE VIRTUAL TABLE doc_fts USING fts5(
        source_id UNINDEXED,
        path UNINDEXED,
        content,
        tokenize = 'trigram'
    )
    """
    async with temp_engine.begin() as conn:
        await conn.execute(text(old_schema))
        await conn.execute(
            text(
                "INSERT INTO doc_fts (source_id, path, content)"
                " VALUES ('s1', 'a.md', 'pre-migration content')"
            )
        )

    await database_module.create_tables()  # runs the migration (drop+recreate)

    async with temp_engine.begin() as conn:
        columns = {
            row[1]
            for row in (
                await conn.execute(text("PRAGMA table_info(doc_fts)"))
            ).fetchall()
        }
        assert "page" in columns

        # The old row is gone -- expected, since recreating doc_fts empties
        # it; rebuild_check._check_keyword_schema_version() is what forces
        # a full reindex to repopulate it, not this migration itself.
        result = await conn.execute(text("SELECT COUNT(*) FROM doc_fts"))
        assert result.scalar_one() == 0

        # New inserts with an explicit page work post-migration.
        await conn.execute(
            text(
                "INSERT INTO doc_fts (source_id, path, page, content)"
                " VALUES ('s1', 'b.pdf', 2, 'post-migration content')"
            )
        )
        result = await conn.execute(
            text("SELECT page FROM doc_fts WHERE path = 'b.pdf'")
        )
        assert result.scalar_one() == 2


async def test_create_tables_leaves_already_migrated_doc_fts_untouched(temp_engine):
    """Calling create_tables() again (e.g. on every backend restart) once
    doc_fts already has the `page` column must not drop existing rows —
    only a *missing* column triggers the recreate."""
    await database_module.create_tables()
    async with temp_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO doc_fts (source_id, path, page, content)"
                " VALUES ('s1', 'a.md', NULL, 'already migrated content')"
            )
        )

    await database_module.create_tables()  # simulates a second startup

    async with temp_engine.begin() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM doc_fts"))
        assert result.scalar_one() == 1
