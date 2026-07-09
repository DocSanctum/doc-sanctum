from __future__ import annotations

import backend.app.mcp.tools.search_documents as search_documents_module
import pytest
from backend.app.models.source import Source

pytestmark = pytest.mark.asyncio


async def test_search_source_delegates_to_keyword_index_only(monkeypatch):
    """011-keyword-search-fts: _search_source must not touch the source's
    filesystem/remote API at query time — it only queries the keyword index
    built ahead of time by vectorstore/indexer.py (FR-001, contracts/search-contract.md)."""
    calls: list[tuple[list[str], str]] = []

    async def fake_query(source_ids, query_text):
        calls.append((source_ids, query_text))
        return [
            {
                "source_id": source_ids[0],
                "path": "a.md",
                "line_number": 1,
                "line": "hello keyword",
                "context": ["hello keyword"],
            }
        ]

    monkeypatch.setattr(search_documents_module.keyword_client, "query", fake_query)

    source = Source(id="s1", name="demo", type="local", path="/a")
    matches, warning = await search_documents_module._search_source(source, "keyword")

    assert calls == [(["s1"], "keyword")]
    assert warning is None
    assert matches[0]["source_name"] == "demo"
    assert matches[0]["path"] == "a.md"
