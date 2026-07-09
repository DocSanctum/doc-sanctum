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
