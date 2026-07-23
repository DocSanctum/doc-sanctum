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


def _match(
    path: str, source: Source, line_number: int = 1, page: int | None = None
) -> dict:
    return {
        "path": path,
        "source_id": source.id,
        "source_name": source.name,
        "line_number": line_number,
        "line": f"match in {path}",
        "page": page,
        "context": [f"match in {path}"],
    }


@pytest.fixture
def fake_search_source(monkeypatch):
    hits_by_source: dict[str, tuple[list[dict], dict | None]] = {}

    async def _fake(source: Source, query: str):
        return hits_by_source.get(source.id, ([], None))

    monkeypatch.setattr(search_module, "_search_source", _fake)
    return hits_by_source


async def test_search_merges_matches_across_sources(
    session_factory, fake_search_source
):
    s1 = Source(name="s1", type="local", path="/a")
    s2 = Source(name="s2", type="local", path="/b")
    await _insert_source(session_factory, s1)
    await _insert_source(session_factory, s2)

    fake_search_source[s1.id] = ([_match("a.md", s1)], None)
    fake_search_source[s2.id] = ([_match("b.md", s2)], None)

    result = await search_module.search(q="keyword")

    assert {m.path for m in result.matches} == {"a.md", "b.md"}
    assert result.warnings == []


async def test_search_includes_page_for_pdf_match_and_omits_it_for_markdown(
    session_factory, fake_search_source
):
    s1 = Source(name="s1", type="local", path="/a")
    await _insert_source(session_factory, s1)

    fake_search_source[s1.id] = (
        [_match("a.md", s1), _match("b.pdf", s1, page=2)],
        None,
    )

    result = await search_module.search(q="keyword")

    by_path = {m.path: m for m in result.matches}
    assert by_path["a.md"].page is None
    assert by_path["b.pdf"].page == 2


async def test_search_scoped_to_source_id(session_factory, fake_search_source):
    s1 = Source(name="s1", type="local", path="/a")
    s2 = Source(name="s2", type="local", path="/b")
    await _insert_source(session_factory, s1)
    await _insert_source(session_factory, s2)

    fake_search_source[s1.id] = ([_match("a.md", s1)], None)
    fake_search_source[s2.id] = ([_match("b.md", s2)], None)

    result = await search_module.search(q="keyword", source_id=s1.id)

    assert [m.path for m in result.matches] == ["a.md"]


async def test_unknown_source_id_raises_404(session_factory, fake_search_source):
    with pytest.raises(HTTPException) as exc_info:
        await search_module.search(q="keyword", source_id="does-not-exist")
    assert exc_info.value.status_code == 404


async def test_blank_query_raises_400(session_factory, fake_search_source):
    with pytest.raises(HTTPException) as exc_info:
        await search_module.search(q="   ")
    assert exc_info.value.status_code == 400


async def test_no_matches_returns_empty_list(session_factory, fake_search_source):
    s1 = Source(name="s1", type="local", path="/a")
    await _insert_source(session_factory, s1)

    result = await search_module.search(q="keyword")

    assert result.matches == []
    assert result.warnings == []


async def test_warning_from_one_source_does_not_drop_other_results(
    session_factory, fake_search_source
):
    s1 = Source(name="s1", type="local", path="/a")
    s2 = Source(name="s2", type="local", path="/b")
    await _insert_source(session_factory, s1)
    await _insert_source(session_factory, s2)

    fake_search_source[s1.id] = (
        [],
        {"source_id": s1.id, "message": "Source unreachable"},
    )
    fake_search_source[s2.id] = ([_match("b.md", s2)], None)

    result = await search_module.search(q="keyword")

    assert [m.path for m in result.matches] == ["b.md"]
    assert result.warnings[0].source_id == s1.id
