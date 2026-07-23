from __future__ import annotations

import backend.app.keywordindex.client as keywordindex_module
import pytest
import pytest_asyncio
from backend.app.keywordindex.client import (
    MAX_MATCHES_PER_FILE,
    _search_lines,
    delete_document,
    delete_source,
    query,
    upsert_document,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_CREATE_DOC_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS doc_fts USING fts5(
    source_id UNINDEXED,
    path UNINDEXED,
    page UNINDEXED,
    content,
    tokenize = 'trigram'
)
"""


@pytest_asyncio.fixture
async def session_factory(monkeypatch, tmp_path):
    db_path = tmp_path / "test.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(text(_CREATE_DOC_FTS))
    monkeypatch.setattr(keywordindex_module, "async_session_factory", factory)
    yield factory
    await engine.dispose()


# --- _search_lines (moved here from test_mcp_tools.py — the code now lives
# in keywordindex/client.py, since it's the exact-line-matching step run
# against candidate documents narrowed by the FTS query, see query() below) ---


def test_search_lines_basic_match():
    lines = ["Hello world\n", "No match here\n", "Hello again\n"]
    matches = _search_lines(lines, "hello")
    assert len(matches) == 2
    assert matches[0]["line_number"] == 1
    assert matches[1]["line_number"] == 3


def test_search_lines_case_insensitive():
    lines = ["INSTALLATION guide\n", "other line\n"]
    matches = _search_lines(lines, "installation")
    assert len(matches) == 1
    assert "INSTALLATION" in matches[0]["line"]


def test_search_lines_no_match():
    lines = ["foo\n", "bar\n"]
    matches = _search_lines(lines, "xyzzy_nonexistent")
    assert matches == []


def test_search_lines_context_bounds():
    lines = [f"line {i}\n" for i in range(10)]
    lines[0] = "match here\n"
    matches = _search_lines(lines, "match here")
    assert matches[0]["line_number"] == 1
    assert len(matches[0]["context"]) <= 5


def test_search_lines_max_matches_per_file():
    lines = [f"keyword line {i}\n" for i in range(MAX_MATCHES_PER_FILE + 5)]
    matches = _search_lines(lines, "keyword")
    assert len(matches) == MAX_MATCHES_PER_FILE


def test_search_lines_context_includes_surrounding():
    lines = ["before\n", "target match\n", "after\n"]
    matches = _search_lines(lines, "target match")
    assert len(matches) == 1
    ctx = matches[0]["context"]
    assert "before" in ctx[0]
    assert "target match" in ctx[1]
    assert "after" in ctx[2]


# --- upsert_document / delete_document / delete_source ---


@pytest.mark.asyncio
async def test_upsert_then_query_finds_document(session_factory):
    await upsert_document("s1", "a.md", [(None, "hello keyword search world")])
    hits = await query(["s1"], "keyword")
    assert [h["path"] for h in hits] == ["a.md"]


@pytest.mark.asyncio
async def test_upsert_replaces_previous_content(session_factory):
    await upsert_document("s1", "a.md", [(None, "old content here")])
    await upsert_document("s1", "a.md", [(None, "new content here")])
    hits_old = await query(["s1"], "old content")
    hits_new = await query(["s1"], "new content")
    assert hits_old == []
    assert [h["path"] for h in hits_new] == ["a.md"]


@pytest.mark.asyncio
async def test_delete_document_removes_it_from_results(session_factory):
    await upsert_document("s1", "a.md", [(None, "hello keyword world")])
    await delete_document("s1", "a.md")
    hits = await query(["s1"], "keyword")
    assert hits == []


# --- Per-page storage (PDF support) ---


@pytest.mark.asyncio
async def test_upsert_document_with_none_page_produces_single_row(session_factory):
    """A Markdown-shaped call (single (None, text) entry) must still store
    exactly one row, unchanged from before per-page support existed."""
    await upsert_document("s1", "a.md", [(None, "hello keyword world")])
    hits = await query(["s1"], "keyword")
    assert len(hits) == 1
    assert hits[0]["page"] is None


@pytest.mark.asyncio
async def test_upsert_document_with_multiple_pages_stores_one_row_per_page(
    session_factory,
):
    await upsert_document(
        "s1",
        "b.pdf",
        [
            (1, "keyword on page one"),
            (2, "nothing relevant"),
            (3, "keyword on page three"),
        ],
    )
    hits = await query(["s1"], "keyword")
    assert sorted(h["page"] for h in hits) == [1, 3]


@pytest.mark.asyncio
async def test_upsert_document_replaces_all_pages_of_previous_version(session_factory):
    await upsert_document(
        "s1", "b.pdf", [(1, "old keyword text"), (2, "more old keyword text")]
    )
    await upsert_document("s1", "b.pdf", [(1, "new content only")])
    old_hits = await query(["s1"], "old keyword")
    new_hits = await query(["s1"], "new content")
    assert old_hits == []
    assert [h["page"] for h in new_hits] == [1]


@pytest.mark.asyncio
async def test_delete_document_removes_every_page_row_in_one_call(session_factory):
    await upsert_document(
        "s1", "b.pdf", [(1, "keyword page one"), (2, "keyword page two")]
    )
    await delete_document("s1", "b.pdf")
    assert await query(["s1"], "keyword") == []


@pytest.mark.asyncio
async def test_delete_source_removes_all_its_documents(session_factory):
    await upsert_document("s1", "a.md", [(None, "hello keyword world")])
    await upsert_document("s1", "b.md", [(None, "another keyword doc")])
    await upsert_document("s2", "c.md", [(None, "unrelated keyword doc")])
    await delete_source("s1")
    assert await query(["s1"], "keyword") == []
    assert [h["path"] for h in await query(["s2"], "keyword")] == ["c.md"]


# --- query(): candidate narrowing across sources, short-query fallback ---


@pytest.mark.asyncio
async def test_query_scopes_to_given_source_ids(session_factory):
    await upsert_document("s1", "a.md", [(None, "shared keyword here")])
    await upsert_document("s2", "b.md", [(None, "shared keyword here")])
    hits = await query(["s1"], "keyword")
    assert [h["source_id"] for h in hits] == ["s1"]


@pytest.mark.asyncio
async def test_query_searches_multiple_source_ids_at_once(session_factory):
    await upsert_document("s1", "a.md", [(None, "shared keyword here")])
    await upsert_document("s2", "b.md", [(None, "shared keyword here")])
    await upsert_document("s3", "c.md", [(None, "no match here")])
    hits = await query(["s1", "s2"], "keyword")
    assert {h["source_id"] for h in hits} == {"s1", "s2"}


@pytest.mark.asyncio
async def test_query_matches_substring_inside_longer_word(session_factory):
    await upsert_document("s1", "a.md", [(None, "메모리게임 관련 문서")])
    hits = await query(["s1"], "게임")  # 2 chars: exercises the short-query fallback
    assert [h["path"] for h in hits] == ["a.md"]


@pytest.mark.asyncio
async def test_query_short_query_still_finds_match_without_fts(session_factory):
    # "게임" is 2 characters — shorter than the trigram tokenizer's minimum,
    # so this only works via the non-FTS fallback scan (research.md §3).
    await upsert_document("s1", "a.md", [(None, "이건 게임 문서입니다")])
    hits = await query(["s1"], "게임")
    assert [h["path"] for h in hits] == ["a.md"]


@pytest.mark.asyncio
async def test_query_no_match_returns_empty(session_factory):
    await upsert_document("s1", "a.md", [(None, "nothing relevant")])
    assert await query(["s1"], "완전히다른단어") == []


@pytest.mark.asyncio
async def test_query_empty_source_ids_returns_empty(session_factory):
    assert await query([], "keyword") == []


# --- Persistence across restart (US2, spec.md) — doc_fts lives in the same
# SQLite file as the rest of the app, unlike the vector store's in-process
# EphemeralClient, so a fresh engine pointed at the same file must see it. ---


@pytest.mark.asyncio
async def test_index_survives_a_fresh_engine_on_the_same_db_file(monkeypatch, tmp_path):
    db_path = tmp_path / "restart.sqlite3"

    engine1 = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    factory1 = async_sessionmaker(engine1, expire_on_commit=False)
    async with engine1.begin() as conn:
        await conn.execute(text(_CREATE_DOC_FTS))
    monkeypatch.setattr(keywordindex_module, "async_session_factory", factory1)
    await upsert_document("s1", "a.md", [(None, "keyword search survives restart")])
    await engine1.dispose()

    # A brand new engine/session factory on the same file stands in for the
    # backend process restarting — nothing above is reused past this point.
    engine2 = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    factory2 = async_sessionmaker(engine2, expire_on_commit=False)
    monkeypatch.setattr(keywordindex_module, "async_session_factory", factory2)

    hits = await query(["s1"], "keyword")

    assert [h["path"] for h in hits] == ["a.md"]
    await engine2.dispose()
