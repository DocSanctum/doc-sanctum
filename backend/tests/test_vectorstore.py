from __future__ import annotations

import backend.app.vectorstore.client as client_module
import backend.app.vectorstore.indexer as indexer_module
import pytest
from backend.app.models.source import Source
from backend.app.vectorstore.chunker import MAX_CHUNK_CHARS, chunk_markdown

# --- Chunker (research.md §3 / FR-001 chunk-based indexing) ---


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


def test_chunk_markdown_respects_max_chars_for_oversized_paragraph():
    long_para = "word " * 500  # single paragraph, no blank lines, well over the limit
    text = f"# Title\n\n{long_para}\n"
    chunks = chunk_markdown(text)
    assert len(chunks) > 1
    assert all(len(c.text) <= MAX_CHUNK_CHARS for c in chunks)


def test_chunk_markdown_no_empty_chunks():
    text = "# A\n\n\n\n## B\n\ncontent\n\n\n\n"
    chunks = chunk_markdown(text)
    assert all(c.text.strip() for c in chunks)


# --- Client init_engine() deployment-mode branching (004 research.md §1, §5) ---


class _FakeEmbeddingFunction:
    def __call__(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]


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
def reset_engine_state():
    client_module._client = None
    client_module._embedding_function = None
    client_module._engine_available = False
    yield
    client_module._client = None
    client_module._embedding_function = None
    client_module._engine_available = False


def test_init_engine_standalone_uses_ephemeral_client(monkeypatch):
    monkeypatch.setattr(client_module.settings, "deployment_mode", "standalone")
    monkeypatch.setattr(
        client_module, "DefaultEmbeddingFunction", lambda: _FakeEmbeddingFunction()
    )
    calls: dict[str, object] = {}

    class FakeChroma:
        @staticmethod
        def EphemeralClient():
            calls["ephemeral"] = True
            return object()

        @staticmethod
        def HttpClient(host, port):  # pragma: no cover - must not be called
            calls["http"] = (host, port)
            return _FakeHttpClient(host, port)

    monkeypatch.setattr(client_module, "chromadb", FakeChroma)

    assert client_module.init_engine() is True
    assert calls.get("ephemeral") is True
    assert "http" not in calls


def test_init_engine_scaleout_connects_via_http_client(monkeypatch):
    monkeypatch.setattr(client_module.settings, "deployment_mode", "scaleout")
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


def test_init_engine_scaleout_raises_when_unreachable(monkeypatch):
    monkeypatch.setattr(client_module.settings, "deployment_mode", "scaleout")
    monkeypatch.setattr(client_module.settings, "vector_store_host", "vectorstore")
    monkeypatch.setattr(client_module.settings, "vector_store_port", 8000)
    monkeypatch.setattr(
        client_module, "DefaultEmbeddingFunction", lambda: _FakeEmbeddingFunction()
    )

    class FakeChroma:
        @staticmethod
        def HttpClient(host, port):
            return _FakeHttpClient(host, port, heartbeat_ok=False)

    monkeypatch.setattr(client_module, "chromadb", FakeChroma)

    with pytest.raises(Exception):
        client_module.init_engine()
    assert client_module.is_engine_available() is False


def test_init_engine_standalone_failure_is_swallowed_not_raised(monkeypatch):
    """standalone must keep 003's FR-014 behavior: failures degrade to
    `False` (surfaced later as a 503 at registration) instead of crashing."""
    monkeypatch.setattr(client_module.settings, "deployment_mode", "standalone")

    def boom():
        raise RuntimeError("embedding model missing")

    monkeypatch.setattr(client_module, "DefaultEmbeddingFunction", boom)

    assert client_module.init_engine() is False
    assert client_module.is_engine_available() is False


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


def _source(source_id: str = "src-1") -> Source:
    return Source(id=source_id, name="demo", type="local", path="/tmp/whatever")


@pytest.fixture(autouse=True)
def reset_doc_hashes():
    indexer_module._doc_hashes.clear()
    yield
    indexer_module._doc_hashes.clear()


@pytest.fixture
def fake_client(monkeypatch):
    fake = _FakeVectorClient()
    monkeypatch.setattr(indexer_module, "client", fake)
    return fake


@pytest.mark.asyncio
async def test_index_document_success_records_hash(fake_client, monkeypatch):
    async def fake_read_with_cache(source, path):
        return "# Heading\n\nSome content here.", None

    monkeypatch.setattr(indexer_module, "read_with_cache", fake_read_with_cache)

    warning = await indexer_module._index_document(_source(), "a.md")

    assert warning is None
    assert fake_client.upserted == [("src-1", "a.md", 1)]
    assert indexer_module._doc_hashes["src-1"]["a.md"]


@pytest.mark.asyncio
async def test_index_document_failure_returns_warning_without_upsert(
    fake_client, monkeypatch
):
    async def fake_read_with_cache(source, path):
        raise ValueError("File not found: a.md")

    monkeypatch.setattr(indexer_module, "read_with_cache", fake_read_with_cache)

    warning = await indexer_module._index_document(_source(), "a.md")

    assert warning is not None
    assert warning["path"] == "a.md"
    assert fake_client.upserted == []


@pytest.mark.asyncio
async def test_sync_source_index_skips_unchanged_reindexes_changed_removes_deleted(
    fake_client, monkeypatch
):
    docs = [{"path": "a.md"}, {"path": "b.md"}]
    contents = {"a.md": "content A", "b.md": "content B"}

    async def fake_list_documents(source):
        return list(docs)

    async def fake_read_with_cache(source, path):
        return contents[path], None

    monkeypatch.setattr(indexer_module, "_list_documents", fake_list_documents)
    monkeypatch.setattr(indexer_module, "read_with_cache", fake_read_with_cache)

    source = _source()

    # First sync: both documents are new -> both indexed
    await indexer_module.sync_source_index(source)
    assert len(fake_client.upserted) == 2

    # Second sync, nothing changed -> no re-upsert
    fake_client.upserted.clear()
    await indexer_module.sync_source_index(source)
    assert fake_client.upserted == []

    # a.md content changes, b.md disappears from the tree
    contents["a.md"] = "content A changed"
    docs.clear()
    docs.append({"path": "a.md"})
    await indexer_module.sync_source_index(source)

    assert fake_client.upserted == [("src-1", "a.md", 1)]
    assert ("src-1", "b.md") in fake_client.deleted_docs


@pytest.mark.asyncio
async def test_remove_document_clears_hash_and_deletes(fake_client):
    indexer_module._doc_hashes["src-1"] = {"a.md": "somehash"}

    await indexer_module.remove_document(_source(), "a.md")

    assert "a.md" not in indexer_module._doc_hashes.get("src-1", {})
    assert fake_client.deleted_docs == [("src-1", "a.md")]


@pytest.mark.asyncio
async def test_delete_source_index_clears_all_state(fake_client):
    indexer_module._doc_hashes["src-1"] = {"a.md": "somehash"}

    await indexer_module.delete_source_index("src-1")

    assert fake_client.deleted_collections == ["src-1"]
    assert "src-1" not in indexer_module._doc_hashes


@pytest.mark.asyncio
async def test_create_index_raises_when_engine_unavailable(fake_client, monkeypatch):
    fake_client.engine_available = False

    async def fake_list_documents(source):
        return []

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
