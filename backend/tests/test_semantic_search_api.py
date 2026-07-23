from __future__ import annotations

import backend.app.api.search as search_module
import pytest
import pytest_asyncio
from backend.app.models.source import Source
from fastapi import HTTPException
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
    monkeypatch.setattr(search_module, "async_session_factory", factory)
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
def fake_vector_client(monkeypatch):
    fake = _FakeVectorClient()
    monkeypatch.setattr(search_module, "vector_client", fake)
    return fake


def _hit(path: str, source: Source, score: float, page: int | None = None) -> dict:
    return {
        "path": path,
        "source_id": source.id,
        "source_name": source.name,
        "chunk_index": 0,
        "page": page,
        "score": score,
        "excerpt": f"excerpt of {path}",
    }


async def test_ranks_hits_across_sources_by_score(session_factory, fake_vector_client):
    s1 = Source(name="s1", type="local", path="/a")
    s2 = Source(name="s2", type="local", path="/b")
    await _insert_source(session_factory, s1)
    await _insert_source(session_factory, s2)

    fake_vector_client.hits_by_source = {
        s1.id: [_hit("low.md", s1, 0.2)],
        s2.id: [_hit("high.md", s2, 0.9)],
    }

    result = await search_module.semantic_search(q="query")

    assert [r.path for r in result.results] == ["high.md", "low.md"]
    assert result.warnings == []


async def test_semantic_search_includes_page_for_pdf_hit_and_omits_it_for_markdown(
    session_factory, fake_vector_client
):
    s1 = Source(name="s1", type="local", path="/a")
    await _insert_source(session_factory, s1)

    fake_vector_client.hits_by_source = {
        s1.id: [_hit("a.md", s1, 0.5), _hit("b.pdf", s1, 0.9, page=2)],
    }

    result = await search_module.semantic_search(q="query")

    by_path = {r.path: r for r in result.results}
    assert by_path["a.md"].page is None
    assert by_path["b.pdf"].page == 2


async def test_source_id_scopes_results(session_factory, fake_vector_client):
    s1 = Source(name="s1", type="local", path="/a")
    s2 = Source(name="s2", type="local", path="/b")
    await _insert_source(session_factory, s1)
    await _insert_source(session_factory, s2)

    fake_vector_client.hits_by_source = {
        s1.id: [_hit("a.md", s1, 0.5)],
        s2.id: [_hit("b.md", s2, 0.9)],
    }

    result = await search_module.semantic_search(q="query", source_id=s1.id)

    assert [r.path for r in result.results] == ["a.md"]


async def test_unknown_source_id_raises_404(session_factory, fake_vector_client):
    with pytest.raises(HTTPException) as exc_info:
        await search_module.semantic_search(q="query", source_id="does-not-exist")
    assert exc_info.value.status_code == 404


async def test_blank_query_raises_400(session_factory, fake_vector_client):
    with pytest.raises(HTTPException) as exc_info:
        await search_module.semantic_search(q="   ")
    assert exc_info.value.status_code == 400


async def test_no_matches_returns_empty_list(session_factory, fake_vector_client):
    s1 = Source(name="s1", type="local", path="/a")
    await _insert_source(session_factory, s1)

    result = await search_module.semantic_search(q="query")

    assert result.results == []
    assert result.warnings == []


async def test_engine_unavailable_returns_warning(session_factory, fake_vector_client):
    s1 = Source(name="s1", type="local", path="/a")
    await _insert_source(session_factory, s1)
    fake_vector_client.engine_available = False

    result = await search_module.semantic_search(q="query")

    assert result.results == []
    assert result.warnings[0].reason == "engine_unavailable"
    assert result.warnings[0].source_id is None


async def test_top_k_limits_merged_results(session_factory, fake_vector_client):
    s1 = Source(name="s1", type="local", path="/a")
    await _insert_source(session_factory, s1)

    fake_vector_client.hits_by_source = {
        s1.id: [_hit(f"{i}.md", s1, 1.0 - i * 0.1) for i in range(10)]
    }

    result = await search_module.semantic_search(q="query", top_k=3)

    assert len(result.results) == 3
