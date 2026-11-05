from __future__ import annotations

import backend.app.services.document_access as document_access_module
import httpx
import pytest
from backend.app.main import app
from backend.app.models.source import Source


def _local_source(root: str) -> Source:
    return Source(
        id="local-1",
        name="local",
        type="local",
        path=root,
        polling_interval_seconds=None,
        created_at="2026-01-01T00:00:00+00:00",
        status="active",
        error_message=None,
    )


@pytest.mark.asyncio
async def test_foreign_host_header_is_rejected():
    """A DNS-rebinding page reaches the backend under its own domain, so any
    Host outside the allowlist must be refused before routing."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://evil.example"
    ) as client:
        api = await client.get("/api/v1/deployment")
        mcp = await client.post("/mcp", json={})
    assert api.status_code == 400
    assert mcp.status_code == 400


@pytest.mark.asyncio
async def test_localhost_host_header_is_accepted():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://localhost:8000"
    ) as client:
        resp = await client.get("/api/v1/deployment")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_read_rejects_non_document_files_under_source_root(tmp_path):
    """Files under a source root that are not indexable documents (secrets,
    keys, configs) must not be readable through the document read path."""
    (tmp_path / ".env").write_text("SECRET=1")
    (tmp_path / "notes.md").write_text("# Notes")
    source = _local_source(str(tmp_path))

    with pytest.raises(ValueError, match="Unsupported document type"):
        await document_access_module.read_with_cache(source, ".env")
    with pytest.raises(ValueError, match="Unsupported document type"):
        await document_access_module.read_raw_with_cache(source, ".env")

    extracted, _ = await document_access_module.read_with_cache(source, "notes.md")
    assert extracted.text == "# Notes"
