from __future__ import annotations

import asyncio
from pathlib import Path

import backend.app.vectorstore.client as client_module
import backend.app.vectorstore.hash_cache as hash_cache_module
import backend.app.vectorstore.indexer as indexer_module
import backend.app.vectorstore.tokenizer as tokenizer_module
import pytest
import pytest_asyncio
from backend.app.models.source import Source
from backend.app.vectorstore.chunker import MAX_CHUNK_TOKENS, chunk_markdown
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# --- Chunker ---


def test_chunk_markdown_empty():
    assert chunk_markdown("") == []
    assert chunk_markdown("   \n  ") == []


def test_chunk_markdown_splits_by_heading():
    text = (
        "# Title\n\nIntro.\n\n"
        "## Section A\n\nContent A.\n\n"
        "## Section B\n\nContent B.\n"
    )
    chunks = chunk_markdown(text)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    joined = " ".join(c.text for c in chunks)
    assert "Section A" in joined
    assert "Section B" in joined


def test_chunk_markdown_respects_max_tokens_for_oversized_paragraph():
    long_para = "word " * 500  # single paragraph, no blank lines, well over the limit
    text = f"# Title\n\n{long_para}\n"
    chunks = chunk_markdown(text)
    assert len(chunks) > 1
    assert all(
        tokenizer_module.count_tokens(c.text) <= MAX_CHUNK_TOKENS for c in chunks
    )


def test_chunk_markdown_no_empty_chunks():
    text = "# A\n\n\n\n## B\n\ncontent\n\n\n\n"
    chunks = chunk_markdown(text)
    assert all(c.text.strip() for c in chunks)


def test_chunk_markdown_preserves_tail_content_of_dense_korean_section():
    """This is a chunker-level proxy for "search finds the tail content":
    test_semantic_search_api.py's tests are fully mocked at the
    vector-client layer (query() returns canned hits, no real
    chunking/embedding happens), so they can't exercise the actual defect.
    What search can return is bounded by what got embedded, which is
    bounded by what chunk_markdown() produced — so proving the tail content
    survives verbatim into a chunk's `.text` here is the correct,
    deterministic place to prove the defect (content silently dropped
    before embedding) is fixed, without standing up a real chromadb
    instance in a unit test."""
    dense_korean = (
        "분산 시스템에서 일관성과 가용성 사이의 트레이드오프는 설계 초기 단계부터 "
        "신중하게 검토되어야 하는 핵심 요소이며, 특히 네트워크 파티션이 발생했을 때 "
        "시스템이 어떻게 동작해야 하는지에 대한 명확한 정책이 필요하다. "
    ) * 6
    tail_marker = "이것은문서끝부분에만있는고유한마커텍스트입니다"
    text = f"# 개요\n\n{dense_korean}{tail_marker}\n"
    chunks = chunk_markdown(text)
    assert any(tail_marker in c.text for c in chunks)


def test_chunk_markdown_dense_korean_section_stays_within_token_limit():
    """Dense Korean text packs far more tokens per character than English
    (measured here at roughly 1.4 tokens/char vs. roughly 0.16 for
    English) — a section whose 800-character chunk would have fit under
    the old char-based sizing must still be split under the new
    token-based sizing so no chunk silently exceeds the embedding model's
    real token capacity."""
    dense_korean = (
        "분산 시스템에서 일관성과 가용성 사이의 트레이드오프는 설계 초기 단계부터 "
        "신중하게 검토되어야 하는 핵심 요소이며, 특히 네트워크 파티션이 발생했을 때 "
        "시스템이 어떻게 동작해야 하는지에 대한 명확한 정책이 필요하다. "
    ) * 6
    text = f"# 개요\n\n{dense_korean}\n"
    chunks = chunk_markdown(text)
    assert len(chunks) > 1
    assert all(
        tokenizer_module.count_tokens(c.text) <= MAX_CHUNK_TOKENS for c in chunks
    )


def test_chunk_markdown_no_more_chunks_than_old_char_based_baseline():
    """Baseline counts were measured once against the pre-change
    character-based chunker (MAX_CHUNK_CHARS=800 / CHUNK_OVERLAP_CHARS=100)
    for three representative English fixtures; the token-based chunker
    must not produce more chunks than that baseline for any of them."""
    sample_doc = (
        Path(__file__).resolve().parents[1] / "sample-docs" / "01.Welcome.md"
    ).read_text()

    long_paragraph_doc = (
        "# Title\n\n"
        + (
            "The quick brown fox jumps over the lazy dog near the river bank "
            "every single morning. "
        )
        * 60
        + "\n"
    )

    multi_section_doc = "".join(
        f"## Section {i}\n\n"
        + (
            "This is a normal paragraph of English documentation text "
            "explaining something useful. "
        )
        * 8
        + "\n\n"
        for i in range(10)
    )

    baselines = {
        # Re-measured after 01.Welcome.md grew a Diagrams section: the old
        # char-based chunker produces 9 chunks for the current file content.
        "sample_doc (01.Welcome.md)": (sample_doc, 9),
        "long_paragraph_doc": (long_paragraph_doc, 9),
        "multi_section_doc": (multi_section_doc, 10),
    }
    for name, (doc, old_count) in baselines.items():
        new_count = len(chunk_markdown(doc))
        assert new_count <= old_count, (
            f"{name}: token-based chunker produced {new_count} chunks, "
            f"more than the {old_count}-chunk char-based baseline"
        )


# --- Client init_engine(): both deployment modes share one persistent
# HttpClient path, with a bounded retry budget instead of a mode-based
# branch that could crash startup ---


class _FakeEmbeddingFunction:
    def __call__(self, texts: list[str]) -> list[list[float]]:
        return [[0.0, 0.0] for _ in texts]


class _FakeHttpClient:
    def __init__(self, host: str, port: int, heartbeat_ok: bool = True) -> None:
        self.host = host
        self.port = port
        self._heartbeat_ok = heartbeat_ok

    def heartbeat(self) -> int:
        if not self._heartbeat_ok:
            raise ConnectionError("cannot reach shared vector store")
        return 1


@pytest.fixture(autouse=True)
def reset_engine_state(monkeypatch):
    client_module._client = None
    client_module._embedding_function = None
    client_module._embedding_dimension = None
    client_module._engine_available = False
    # Keep retry tests fast — no real sleeping.
    monkeypatch.setattr(client_module.time, "sleep", lambda _seconds: None)
    yield
    client_module._client = None
    client_module._embedding_function = None
    client_module._embedding_dimension = None
    client_module._engine_available = False


def test_init_engine_connects_via_http_client_regardless_of_mode(monkeypatch):
    monkeypatch.setattr(client_module.settings, "vector_store_host", "vectorstore")
    monkeypatch.setattr(client_module.settings, "vector_store_port", 8000)
    monkeypatch.setattr(
        client_module, "DefaultEmbeddingFunction", lambda: _FakeEmbeddingFunction()
    )

    class FakeChroma:
        @staticmethod
        def HttpClient(host, port):
            assert (host, port) == ("vectorstore", 8000)
            return _FakeHttpClient(host, port, heartbeat_ok=True)

    monkeypatch.setattr(client_module, "chromadb", FakeChroma)

    assert client_module.init_engine() is True
    assert client_module.is_engine_available() is True
    assert client_module.embedding_signature() == "_FakeEmbeddingFunction:2"


def test_init_engine_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(
        client_module, "DefaultEmbeddingFunction", lambda: _FakeEmbeddingFunction()
    )
    attempts: list[int] = []

    class FakeChroma:
        @staticmethod
        def HttpClient(host, port):
            attempts.append(1)
            return _FakeHttpClient(host, port, heartbeat_ok=len(attempts) >= 3)

    monkeypatch.setattr(client_module, "chromadb", FakeChroma)

    assert client_module.init_engine() is True
    assert len(attempts) == 3


def test_init_engine_gives_up_without_raising_after_exhausting_retries(monkeypatch):
    """A persistent connection failure must never crash the caller — it
    degrades to is_engine_available() == False so the rest of the app keeps
    starting."""
    monkeypatch.setattr(
        client_module, "DefaultEmbeddingFunction", lambda: _FakeEmbeddingFunction()
    )

    class FakeChroma:
        @staticmethod
        def HttpClient(host, port):
            return _FakeHttpClient(host, port, heartbeat_ok=False)

    monkeypatch.setattr(client_module, "chromadb", FakeChroma)

    assert client_module.init_engine() is False  # must not raise
    assert client_module.is_engine_available() is False


def test_init_engine_embedding_function_failure_returns_false_without_raising(
    monkeypatch,
):
    def boom():
        raise RuntimeError("embedding model missing")

    monkeypatch.setattr(client_module, "DefaultEmbeddingFunction", boom)

    assert client_module.init_engine() is False
    assert client_module.is_engine_available() is False


# --- Background reconnect: recovers once the vector store comes back,
# without needing a full backend restart ---


def test_try_reconnect_once_succeeds_once_vector_store_is_reachable(monkeypatch):
    monkeypatch.setattr(
        client_module, "DefaultEmbeddingFunction", lambda: _FakeEmbeddingFunction()
    )

    class AlwaysFailingChroma:
        @staticmethod
        def HttpClient(host, port):
            return _FakeHttpClient(host, port, heartbeat_ok=False)

    monkeypatch.setattr(client_module, "chromadb", AlwaysFailingChroma)
    assert client_module.init_engine() is False  # exhausts startup retries

    class NowHealthyChroma:
        @staticmethod
        def HttpClient(host, port):
            return _FakeHttpClient(host, port, heartbeat_ok=True)

    monkeypatch.setattr(client_module, "chromadb", NowHealthyChroma)
    assert client_module._try_reconnect_once() is True
    assert client_module.is_engine_available() is True


def test_try_reconnect_once_is_a_noop_when_embedding_function_never_initialized(
    monkeypatch,
):
    def boom():
        raise RuntimeError("embedding model missing")

    monkeypatch.setattr(client_module, "DefaultEmbeddingFunction", boom)
    assert client_module.init_engine() is False

    # Nothing to reconnect to — the embedding function itself never came up.
    assert client_module._try_reconnect_once() is False


@pytest.mark.asyncio
async def test_reconnect_loop_retries_until_available(monkeypatch):
    monkeypatch.setattr(
        client_module, "DefaultEmbeddingFunction", lambda: _FakeEmbeddingFunction()
    )
    attempts: list[int] = []

    class FlakyThenHealthyChroma:
        @staticmethod
        def HttpClient(host, port):
            attempts.append(1)
            return _FakeHttpClient(host, port, heartbeat_ok=False)

    monkeypatch.setattr(client_module, "chromadb", FlakyThenHealthyChroma)
    assert client_module.init_engine() is False  # exhausts startup retries first

    sleep_calls: list[float] = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)
        if len(sleep_calls) == 2:
            # Vector store "comes back" right before the loop's next attempt.
            class NowHealthyChroma:
                @staticmethod
                def HttpClient(host, port):
                    return _FakeHttpClient(host, port, heartbeat_ok=True)

            monkeypatch.setattr(client_module, "chromadb", NowHealthyChroma)

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)

    await client_module.reconnect_loop()

    assert client_module.is_engine_available() is True
    assert len(sleep_calls) == 2  # stopped retrying once reconnected


# --- Indexer (FR-009 partial failure, FR-010 targeted reindex, FR-012 cleanup) ---


class _FakeVectorClient:
    def __init__(self, engine_available: bool = True) -> None:
        self.engine_available = engine_available
        self.upserted: list[tuple[str, str, int]] = []
        self.deleted_docs: list[tuple[str, str]] = []
        self.deleted_collections: list[str] = []

    def init_engine(self) -> bool:
        return self.engine_available

    async def upsert_chunks(self, source_id, source_name, path, chunks) -> None:
        self.upserted.append((source_id, path, len(chunks)))

    async def delete_document(self, source_id, path) -> None:
        self.deleted_docs.append((source_id, path))

    async def delete_collection(self, source_id) -> None:
        self.deleted_collections.append(source_id)


class _FakeKeywordClient:
    """Stands in for keywordindex/client.py here — that module's own upsert/
    delete/query behavior is covered by test_keywordindex.py; these indexer
    tests only need indexer.py's calls into it to not hit a real database."""

    def __init__(self) -> None:
        self.upserted: list[tuple[str, str]] = []
        self.deleted_docs: list[tuple[str, str]] = []
        self.deleted_sources: list[str] = []

    async def upsert_document(self, source_id, path, content) -> None:
        self.upserted.append((source_id, path))

    async def delete_document(self, source_id, path) -> None:
        self.deleted_docs.append((source_id, path))

    async def delete_source(self, source_id) -> None:
        self.deleted_sources.append(source_id)


def _source(source_id: str = "src-1") -> Source:
    return Source(id=source_id, name="demo", type="local", path="/tmp/whatever")


@pytest_asyncio.fixture
async def hash_cache_db(monkeypatch, tmp_path):
    """The hash cache is now durable SQLite instead of the old in-process
    _doc_hashes/_doc_shas dicts, so indexer tests that reach it need a real
    (temp) database behind it."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.sqlite3'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS doc_index_cache (
                source_id TEXT NOT NULL, path TEXT NOT NULL, content_hash TEXT,
                blob_sha TEXT, sync_state TEXT NOT NULL DEFAULT 'clean',
                updated_at TEXT NOT NULL, PRIMARY KEY (source_id, path)
            )
        """)
        )
    monkeypatch.setattr(hash_cache_module, "async_session_factory", factory)
    yield factory
    await engine.dispose()


@pytest.fixture
def fake_client(monkeypatch):
    fake = _FakeVectorClient()
    fake.keyword = _FakeKeywordClient()
    monkeypatch.setattr(indexer_module, "client", fake)
    monkeypatch.setattr(indexer_module, "keyword_client", fake.keyword)
    return fake


@pytest.mark.asyncio
async def test_index_document_success_records_hash(
    hash_cache_db, fake_client, monkeypatch
):
    async def fake_read_with_cache(source, path):
        return "# Heading\n\nSome content here.", None

    monkeypatch.setattr(indexer_module, "read_with_cache", fake_read_with_cache)

    warning = await indexer_module._index_document(_source(), "a.md")

    assert warning is None
    assert fake_client.upserted == [("src-1", "a.md", 1)]
    assert fake_client.keyword.upserted == [("src-1", "a.md")]
    hashes, _ = await hash_cache_module.get_known("src-1")
    assert hashes["a.md"]


@pytest.mark.asyncio
async def test_index_document_failure_returns_warning_without_upsert(
    hash_cache_db, fake_client, monkeypatch
):
    async def fake_read_with_cache(source, path):
        raise ValueError("File not found: a.md")

    monkeypatch.setattr(indexer_module, "read_with_cache", fake_read_with_cache)

    warning = await indexer_module._index_document(_source(), "a.md")

    assert warning is not None
    assert warning["path"] == "a.md"
    assert fake_client.upserted == []


@pytest.mark.asyncio
async def test_index_document_write_failure_clears_in_progress_marker(
    hash_cache_db, fake_client, monkeypatch
):
    """A caught failure while the vector store write is in flight (e.g. the
    embedding engine being temporarily unavailable) is a per-document
    warning, not a crash — the 'in_progress' marker it leaves behind must
    be cleared, or the next startup would wrongly treat this source as
    having crashed mid-write and trigger an unnecessary full rebuild."""

    async def fake_read_with_cache(source, path):
        return "# Heading\n\nSome content here.", None

    async def failing_upsert_chunks(source_id, source_name, path, chunks):
        raise RuntimeError("Embedding engine is not available")

    monkeypatch.setattr(indexer_module, "read_with_cache", fake_read_with_cache)
    fake_client.upsert_chunks = failing_upsert_chunks

    warning = await indexer_module._index_document(_source(), "a.md")

    assert warning is not None
    assert warning["reason"] == "index_error"
    assert await hash_cache_module.sources_with_in_progress() == []
    hashes, _ = await hash_cache_module.get_known("src-1")
    assert "a.md" not in hashes


@pytest.mark.asyncio
async def test_sync_source_index_skips_download_when_blob_sha_unchanged(
    hash_cache_db, fake_client, monkeypatch
):
    """github docs carry a blob sha alongside the path. When it matches the
    last-indexed sha, the document must be skipped without ever calling
    read_with_cache (i.e. without downloading its content)."""
    docs = [{"path": "a.md", "sha": "sha-a1"}, {"path": "b.md", "sha": "sha-b1"}]
    contents = {"a.md": "content A", "b.md": "content B"}
    read_calls: list[str] = []

    async def fake_list_documents(source):
        return list(docs), None

    async def fake_read_with_cache(source, path):
        read_calls.append(path)
        return contents[path], None

    monkeypatch.setattr(indexer_module, "_list_documents", fake_list_documents)
    monkeypatch.setattr(indexer_module, "read_with_cache", fake_read_with_cache)

    source = _source()

    # First sync: both new -> each downloaded exactly once and indexed, shas recorded
    await indexer_module.sync_source_index(source)
    assert sorted(read_calls) == ["a.md", "b.md"]
    _, shas = await hash_cache_module.get_known("src-1")
    assert shas == {"a.md": "sha-a1", "b.md": "sha-b1"}

    # Second sync: sha unchanged for both -> no download, no re-upsert at all
    read_calls.clear()
    fake_client.upserted.clear()
    await indexer_module.sync_source_index(source)
    assert read_calls == []
    assert fake_client.upserted == []

    # b.md's blob sha changes upstream -> only b.md is downloaded/reindexed
    docs[1]["sha"] = "sha-b2"
    contents["b.md"] = "content B changed"
    await indexer_module.sync_source_index(source)
    assert read_calls == ["b.md"]
    assert fake_client.upserted == [("src-1", "b.md", 1)]
    _, shas = await hash_cache_module.get_known("src-1")
    assert shas["b.md"] == "sha-b2"


@pytest.mark.asyncio
async def test_sync_source_index_fetches_documents_concurrently(
    hash_cache_db, fake_client, monkeypatch
):
    """Content downloads are the dominant cost of a sync, so candidate documents
    must be fetched concurrently (bounded by _FETCH_CONCURRENCY) rather than one
    strictly after another."""
    docs = [{"path": f"doc{i}.md", "sha": f"sha-{i}"} for i in range(25)]
    in_flight = 0
    max_in_flight = 0

    async def fake_read_with_cache(source, path):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        try:
            # Yield control so overlapping fetches actually pile up in-flight
            # instead of each completing before the next one starts.
            await asyncio.sleep(0.01)
            return f"# {path}\n\nbody", None
        finally:
            in_flight -= 1

    async def fake_list_documents(source):
        return list(docs), None

    monkeypatch.setattr(indexer_module, "_list_documents", fake_list_documents)
    monkeypatch.setattr(indexer_module, "read_with_cache", fake_read_with_cache)

    await indexer_module.sync_source_index(_source())

    # Fetches overlapped (a serial loop would peak at 1) but never exceeded the
    # configured concurrency bound.
    assert max_in_flight > 1
    assert max_in_flight <= indexer_module._FETCH_CONCURRENCY
    assert len(fake_client.upserted) == len(docs)


def test_summarize_index_warnings_maps_status():
    """No warnings -> active; per-document warnings -> partial; a tree-level
    warning (no 'path') -> error, so partial indexing is never silently 'active'."""
    assert indexer_module.summarize_index_warnings([]) == ("active", None)

    status, msg = indexer_module.summarize_index_warnings(
        [{"path": "a.md", "reason": "index_error", "message": "boom"}]
    )
    assert status == "partial"
    assert "1 document" in msg

    status, msg = indexer_module.summarize_index_warnings(
        [{"reason": "rate_limit", "message": "GitHub API rate limit exceeded."}]
    )
    assert status == "error"
    assert "rate limit exceeded" in msg


@pytest.mark.asyncio
async def test_sync_source_index_surfaces_tree_warning_without_pruning(
    hash_cache_db, fake_client, monkeypatch
):
    """A degraded (rate-limited) tree listing returns an empty document list.
    sync must surface that warning AND must NOT prune the previously-indexed
    documents as 'deleted' — otherwise a transient rate limit wipes the index."""
    await hash_cache_module.upsert("src-1", "a.md", "hash-a", "sha-a")
    tree_warning = {
        "source_id": "src-1",
        "reason": "rate_limit",
        "message": "GitHub API rate limit exceeded.",
    }

    async def fake_list_documents(source):
        return [], tree_warning

    monkeypatch.setattr(indexer_module, "_list_documents", fake_list_documents)

    warnings = await indexer_module.sync_source_index(_source())

    assert tree_warning in warnings
    assert fake_client.deleted_docs == []  # nothing pruned despite empty listing
    hashes, _ = await hash_cache_module.get_known("src-1")
    assert "a.md" in hashes


@pytest.mark.asyncio
async def test_remove_document_clears_hash_and_deletes(hash_cache_db, fake_client):
    await hash_cache_module.upsert("src-1", "a.md", "somehash", "someblobsha")

    await indexer_module.remove_document(_source(), "a.md")

    hashes, shas = await hash_cache_module.get_known("src-1")
    assert "a.md" not in hashes
    assert "a.md" not in shas
    assert fake_client.deleted_docs == [("src-1", "a.md")]
    assert fake_client.keyword.deleted_docs == [("src-1", "a.md")]


@pytest.mark.asyncio
async def test_delete_source_index_clears_all_state(hash_cache_db, fake_client):
    await hash_cache_module.upsert("src-1", "a.md", "somehash", "someblobsha")

    await indexer_module.delete_source_index("src-1")

    assert fake_client.deleted_collections == ["src-1"]
    assert fake_client.keyword.deleted_sources == ["src-1"]
    hashes, shas = await hash_cache_module.get_known("src-1")
    assert hashes == {}
    assert shas == {}


@pytest.mark.asyncio
async def test_create_index_raises_when_engine_unavailable(fake_client, monkeypatch):
    fake_client.engine_available = False

    async def fake_list_documents(source):
        return [], None

    monkeypatch.setattr(indexer_module, "_list_documents", fake_list_documents)

    with pytest.raises(indexer_module.EngineUnavailableError):
        await indexer_module.create_index(_source())


@pytest.mark.asyncio
async def test_handle_watch_event_resolves_relative_path(
    fake_client, monkeypatch, tmp_path
):
    root = tmp_path / "docs"
    (root / "sub").mkdir(parents=True)

    calls: list[tuple[str, str]] = []

    async def fake_reindex_document(source, path):
        calls.append(("reindex", path))
        return None

    async def fake_remove_document(source, path):
        calls.append(("remove", path))

    monkeypatch.setattr(indexer_module, "reindex_document", fake_reindex_document)
    monkeypatch.setattr(indexer_module, "remove_document", fake_remove_document)

    source = _source()
    new_file = root / "sub" / "new.md"

    await indexer_module.handle_watch_event(
        source,
        str(root),
        {"event": "file_created", "source_id": "src-1", "path": str(new_file)},
    )
    assert calls == [("reindex", "sub/new.md")]

    calls.clear()
    await indexer_module.handle_watch_event(
        source,
        str(root),
        {"event": "file_deleted", "source_id": "src-1", "path": str(new_file)},
    )
    assert calls == [("remove", "sub/new.md")]
