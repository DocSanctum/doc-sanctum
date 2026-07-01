from __future__ import annotations

import json

import backend.app.mcp.tools.semantic_search_documents as sds_module
import pytest
import pytest_asyncio
from backend.app.models.source import Source
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.asyncio

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
    monkeypatch.setattr(sds_module, "async_session_factory", factory)
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


class _FakeVectorClient:
    def __init__(
        self, engine_available: bool = True, hits_by_source: dict | None = None
    ) -> None:
        self.engine_available = engine_available
        self.hits_by_source = hits_by_source or {}

    def init_engine(self) -> bool:
        return self.engine_available

    async def query(self, source_id, query_text, top_k):
        return list(self.hits_by_source.get(source_id, []))[:top_k]


@pytest.fixture
def fake_client(monkeypatch):
    fake = _FakeVectorClient()
    monkeypatch.setattr(sds_module, "client", fake)
    return fake


def _hit(path: str, source: Source, score: float) -> dict:
    return {
        "path": path,
        "source_id": source.id,
        "source_name": source.name,
        "chunk_index": 0,
        "score": score,
        "excerpt": f"excerpt of {path}",
    }


async def test_ranks_hits_across_sources_by_score(session_factory, fake_client):
    s1 = Source(name="s1", type="local", path="/a")
    s2 = Source(name="s2", type="local", path="/b")
    await _insert_source(session_factory, s1)
    await _insert_source(session_factory, s2)

    fake_client.hits_by_source = {
        s1.id: [_hit("low.md", s1, 0.2)],
        s2.id: [_hit("high.md", s2, 0.9)],
    }

    result = json.loads(await sds_module.semantic_search_documents_handler("query"))

    assert [r["path"] for r in result["results"]] == ["high.md", "low.md"]
    assert result["warnings"] == []


async def test_source_id_filters_scope(session_factory, fake_client):
    s1 = Source(name="s1", type="local", path="/a")
    s2 = Source(name="s2", type="local", path="/b")
    await _insert_source(session_factory, s1)
    await _insert_source(session_factory, s2)

    fake_client.hits_by_source = {
        s1.id: [_hit("a.md", s1, 0.5)],
        s2.id: [_hit("b.md", s2, 0.9)],
    }

    result = json.loads(
        await sds_module.semantic_search_documents_handler("query", source_id=s1.id)
    )

    assert [r["path"] for r in result["results"]] == ["a.md"]


async def test_unknown_source_id_raises(session_factory, fake_client):
    with pytest.raises(ValueError):
        await sds_module.semantic_search_documents_handler(
            "query", source_id="does-not-exist"
        )


async def test_empty_results_when_no_matches(session_factory, fake_client):
    s1 = Source(name="s1", type="local", path="/a")
    await _insert_source(session_factory, s1)

    result = json.loads(await sds_module.semantic_search_documents_handler("query"))

    assert result["results"] == []
    assert result["warnings"] == []


async def test_engine_unavailable_returns_warning(session_factory, fake_client):
    s1 = Source(name="s1", type="local", path="/a")
    await _insert_source(session_factory, s1)
    fake_client.engine_available = False

    result = json.loads(await sds_module.semantic_search_documents_handler("query"))

    assert result["results"] == []
    assert result["warnings"][0]["reason"] == "engine_unavailable"


async def test_top_k_limits_merged_results(session_factory, fake_client):
    s1 = Source(name="s1", type="local", path="/a")
    await _insert_source(session_factory, s1)

    fake_client.hits_by_source = {
        s1.id: [_hit(f"{i}.md", s1, 1.0 - i * 0.1) for i in range(10)]
    }

    result = json.loads(
        await sds_module.semantic_search_documents_handler("query", top_k=3)
    )

    assert len(result["results"]) == 3
