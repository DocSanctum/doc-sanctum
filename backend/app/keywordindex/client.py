from __future__ import annotations

from typing import Any

from sqlalchemy import text

from ..core.database import async_session_factory

MAX_MATCHES_PER_FILE = 10
CONTEXT_LINES = 2

# Bumped whenever doc_fts's schema/row-shape changes in a way that requires
# dropping and recreating the table (see core/database.py — FTS5 tables
# can't be altered in place). rebuild_check._check_keyword_schema_version()
# compares this against a stored setting to detect the change and trigger a
# full reindex, mirroring vectorstore.chunker.CHUNKING_VERSION's pattern.
KEYWORD_INDEX_SCHEMA_VERSION = 1

# The trigram tokenizer can't match anything shorter than 3 characters (no
# full trigram exists for a 1-2 char string) — verified against the real
# SQLite build this project ships with (research.md §3). Below this length,
# query() skips the FTS MATCH step entirely and scans every stored row for
# the given sources instead, still without touching the original source.
_MIN_FTS_QUERY_LEN = 3


def _search_lines(lines: list[str], query: str) -> list[dict[str, Any]]:
    q = query.lower()
    matches = []
    for i, line in enumerate(lines):
        if q in line.lower():
            start = max(0, i - CONTEXT_LINES)
            end = min(len(lines), i + CONTEXT_LINES + 1)
            matches.append(
                {
                    "line_number": i + 1,
                    "line": line.rstrip("\n"),
                    "context": [ln.rstrip("\n") for ln in lines[start:end]],
                }
            )
            if len(matches) >= MAX_MATCHES_PER_FILE:
                break
    return matches


def _fts_phrase(query: str) -> str:
    """Quote a raw query string as a single FTS5 phrase literal, so operators
    (AND/OR/NOT/-, etc.) and embedded quotes in the user's query are treated
    as plain text to match rather than FTS5 query syntax."""
    return '"' + query.replace('"', '""') + '"'


async def upsert_document(
    source_id: str, path: str, pages: list[tuple[int | None, str]]
) -> None:
    """Replace the stored row(s) for (source_id, path) with new content. FTS5
    virtual tables have no unique constraint to upsert against, so this is a
    delete-then-insert, same pattern as the vector store's document replace.

    ``pages`` is a list of (page_number, page_text) — a document with no page
    concept (Markdown) passes a single [(None, whole_text)] entry, matching
    today's one-row-per-document shape; a PDF passes one entry per physical
    page (including blank ones), so a keyword match's row always carries the
    page it came from."""
    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM doc_fts WHERE source_id = :sid AND path = :path"),
            {"sid": source_id, "path": path},
        )
        for page, content in pages:
            await session.execute(
                text(
                    "INSERT INTO doc_fts (source_id, path, page, content) "
                    "VALUES (:sid, :path, :page, :content)"
                ),
                {"sid": source_id, "path": path, "page": page, "content": content},
            )
        await session.commit()


async def delete_document(source_id: str, path: str) -> None:
    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM doc_fts WHERE source_id = :sid AND path = :path"),
            {"sid": source_id, "path": path},
        )
        await session.commit()


async def delete_source(source_id: str) -> None:
    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM doc_fts WHERE source_id = :sid"), {"sid": source_id}
        )
        await session.commit()


async def query(source_ids: list[str], query_text: str) -> list[dict[str, Any]]:
    """Search the given sources' indexed documents for query_text, returning
    hits shaped like _search_lines()'s output plus path/source_id.

    Two-step: narrow candidate (source_id, path) rows via FTS MATCH (skipped
    for queries shorter than _MIN_FTS_QUERY_LEN, where every row for the
    given sources becomes a candidate instead — research.md §3), then
    re-scan each candidate's stored content with _search_lines() for the
    exact line/context output. Never touches the original source — every
    candidate's content already lives in doc_fts."""
    if not source_ids:
        return []

    placeholders = ", ".join(f":sid{i}" for i in range(len(source_ids)))
    params: dict[str, Any] = {f"sid{i}": sid for i, sid in enumerate(source_ids)}

    async with async_session_factory() as session:
        if len(query_text) >= _MIN_FTS_QUERY_LEN:
            params["match"] = _fts_phrase(query_text)
            rows = await session.execute(
                text(
                    "SELECT source_id, path, page, content FROM doc_fts "
                    f"WHERE doc_fts MATCH :match AND source_id IN ({placeholders})"
                ),
                params,
            )
        else:
            rows = await session.execute(
                text(
                    "SELECT source_id, path, page, content FROM doc_fts "
                    f"WHERE source_id IN ({placeholders})"
                ),
                params,
            )
        candidates = rows.all()

    results: list[dict[str, Any]] = []
    for row in candidates:
        lines = row.content.splitlines(keepends=True)
        hits = _search_lines(lines, query_text)
        for hit in hits:
            hit["path"] = row.path
            hit["source_id"] = row.source_id
            hit["page"] = row.page
        results.extend(hits)
    return results
