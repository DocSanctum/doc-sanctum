from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import quote

import backend.app.api.shares as shares_module
import backend.app.core.database as database_module
import backend.app.core.remote_mcp as remote_mcp_module
import httpx
import pytest
import pytest_asyncio
from backend.app.core.database import create_tables, get_session
from backend.app.core.remote_mcp import ListenerGuard
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

REMOTE = "http://192.168.1.10:8100"
LOCAL = "http://localhost:8000"
FIXTURES = Path(__file__).parent / "fixtures"
PNG_BYTES = b"\x89PNG\r\n\x1a\nshared-image"


@pytest_asyncio.fixture
async def env(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "async_session_factory", factory)
    monkeypatch.setattr(shares_module, "async_session_factory", factory)
    await create_tables()

    async def fake_token() -> str:
        return "mcp-token"

    monkeypatch.setattr(remote_mcp_module, "get_or_create_token", fake_token)

    docs = tmp_path / "docs"
    (docs / "team").mkdir(parents=True)
    (docs / "team" / "plan.md").write_text(
        "# Plan\n\nHello **team**.\n\n<script>alert(1)</script>\n\n"
        "![diagram](img/diagram.png)\n\n![remote](https://example.com/x.png)\n",
        encoding="utf-8",
    )
    (docs / "team" / "img").mkdir()
    (docs / "team" / "img" / "diagram.png").write_bytes(PNG_BYTES)
    (docs / "private.png").write_bytes(PNG_BYTES)
    (docs / "secret.md").write_text("# Secret\n", encoding="utf-8")
    shutil.copy(FIXTURES / "sample.pdf", docs / "report.pdf")
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO source (id, name, type, path, created_at) "
                "VALUES ('src1', 'Docs', 'local', :p, '2026-01-01')"
            ),
            {"p": str(docs)},
        )
        await session.commit()

    app = FastAPI()
    app.include_router(shares_module.router, prefix="/api/v1")
    app.include_router(shares_module.viewer_router)

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    guarded = ListenerGuard(app, allowed_hosts=["localhost"], remote_port=8100)
    transport = httpx.ASGITransport(app=guarded)

    def client(base: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=transport, base_url=base)

    yield client, docs
    await engine.dispose()


async def _create(client, path: str, label: str | None = "for Alex") -> dict:
    async with client(LOCAL) as c:
        res = await c.post(
            "/api/v1/shares", json={"source_id": "src1", "path": path, "label": label}
        )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
async def test_teammate_opens_shared_markdown_without_mcp_token(env):
    client, _docs = env
    link = await _create(client, "team/plan.md")
    async with client(REMOTE) as c:
        res = await c.get(f"/share/{link['token']}")
    assert res.status_code == 200
    assert "<strong>team</strong>" in res.text
    # Raw HTML in the document is escaped, never executed.
    assert "<script>" not in res.text
    assert "script-src" not in res.headers["content-security-policy"]
    assert "<span class='folder'>team</span>" in res.text
    assert res.headers["referrer-policy"] == "no-referrer"

    async with client(LOCAL) as c:
        listed = (await c.get("/api/v1/shares")).json()
    assert listed[0]["access_count"] == 1
    assert listed[0]["last_accessed_at"] is not None
    assert listed[0]["label"] == "for Alex"
    assert listed[0]["available"] is True


@pytest.mark.asyncio
async def test_share_token_opens_only_its_own_document(env):
    client, _docs = env
    link = await _create(client, "team/plan.md")
    async with client(REMOTE) as c:
        bogus = await c.get("/share/not-a-real-token")
        nested = await c.get(f"/share/{link['token']}/../secret.md")
        api = await c.get("/api/v1/shares")
        file_read = await c.get(
            "/api/v1/sources/src1/file", params={"path": "secret.md"}
        )
    assert bogus.status_code == 404
    assert nested.status_code == 404
    assert api.status_code == 404
    assert file_read.status_code == 404


@pytest.mark.asyncio
async def test_revoked_link_stops_working(env):
    client, _docs = env
    link = await _create(client, "team/plan.md")
    async with client(LOCAL) as c:
        assert (await c.delete(f"/api/v1/shares/{link['id']}")).status_code == 204
        assert (await c.get("/api/v1/shares")).json() == []
    async with client(REMOTE) as c:
        res = await c.get(f"/share/{link['token']}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_link_to_removed_document_is_invalid(env):
    client, docs = env
    link = await _create(client, "team/plan.md")
    (docs / "team" / "plan.md").unlink()
    async with client(REMOTE) as c:
        res = await c.get(f"/share/{link['token']}")
    assert res.status_code == 404
    async with client(LOCAL) as c:
        listed = (await c.get("/api/v1/shares")).json()
    assert listed[0]["available"] is False


@pytest.mark.asyncio
async def test_shared_pdf_opens_inline(env):
    client, _docs = env
    link = await _create(client, "report.pdf", label=None)
    async with client(REMOTE) as c:
        res = await c.get(f"/share/{link['token']}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"].startswith("inline")


@pytest.mark.asyncio
async def test_create_rejects_unsupported_files_and_unknown_sources(env):
    client, _docs = env
    async with client(LOCAL) as c:
        env_file = await c.post(
            "/api/v1/shares", json={"source_id": "src1", "path": ".env"}
        )
        unknown = await c.post(
            "/api/v1/shares", json={"source_id": "nope", "path": "a.md"}
        )
    assert env_file.status_code == 422
    assert unknown.status_code == 404


@pytest.mark.asyncio
async def test_base_url_setting_round_trips(env, monkeypatch):
    client, _docs = env
    monkeypatch.setenv("SHARE_HOST_HINT", "my-mac.local")
    async with client(LOCAL) as c:
        before = (await c.get("/api/v1/shares/settings")).json()
        after = (
            await c.put(
                "/api/v1/shares/settings", json={"base_url": "http://10.0.0.5:8020/"}
            )
        ).json()
    assert before["base_url"] == ""
    assert before["suggested_base_url"] == "http://my-mac.local:8020"
    assert after["base_url"] == "http://10.0.0.5:8020"


def _asset_url(token: str, path: str) -> str:
    return f"/share/{token}/asset?path={quote(path, safe='')}"


@pytest.mark.asyncio
async def test_shared_page_points_embedded_images_at_the_share_asset_route(env):
    client, _docs = env
    link = await _create(client, "team/plan.md")
    async with client(REMOTE) as c:
        res = await c.get(f"/share/{link['token']}")
    expected = f'src="{link["token"]}/asset?path=team%2Fimg%2Fdiagram.png"'
    assert expected in res.text
    assert 'src="https://example.com/x.png"' in res.text
    assert "img-src 'self'" in res.headers["content-security-policy"]


@pytest.mark.asyncio
async def test_teammate_loads_an_image_the_shared_document_embeds(env):
    client, _docs = env
    link = await _create(client, "team/plan.md")
    async with client(REMOTE) as c:
        res = await c.get(_asset_url(link["token"], "team/img/diagram.png"))
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content == PNG_BYTES
    assert res.headers["referrer-policy"] == "no-referrer"
    assert "sandbox" in res.headers["content-security-policy"]

    # Images do not count as extra views of the shared document.
    async with client(LOCAL) as c:
        listed = (await c.get("/api/v1/shares")).json()
    assert listed[0]["access_count"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path", ["private.png", "team/plan.md", "team/img/../../private.png", ".env"]
)
async def test_share_token_cannot_fetch_files_the_document_does_not_embed(env, path):
    client, _docs = env
    link = await _create(client, "team/plan.md")
    async with client(REMOTE) as c:
        res = await c.get(_asset_url(link["token"], path))
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_revoked_or_bogus_token_cannot_fetch_images(env):
    client, _docs = env
    link = await _create(client, "team/plan.md")
    async with client(LOCAL) as c:
        await c.delete(f"/api/v1/shares/{link['id']}")
    async with client(REMOTE) as c:
        revoked = await c.get(_asset_url(link["token"], "team/img/diagram.png"))
        bogus = await c.get(_asset_url("nope", "team/img/diagram.png"))
        nested = await c.get(f"/share/{link['token']}/asset/extra")
    assert revoked.status_code == 404
    assert bogus.status_code == 404
    assert nested.status_code == 404


@pytest.mark.asyncio
async def test_pdf_share_serves_no_images(env):
    client, _docs = env
    link = await _create(client, "report.pdf", label=None)
    async with client(REMOTE) as c:
        res = await c.get(_asset_url(link["token"], "team/img/diagram.png"))
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_shared_tables_are_wrapped_so_they_scroll_on_phones(env):
    client, docs = env
    (docs / "table.md").write_text(
        "| a | b |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8"
    )
    link = await _create(client, "table.md")
    async with client(REMOTE) as c:
        res = await c.get(f"/share/{link['token']}")
    assert "<div class='table-wrap'><table>" in res.text
    assert "</table></div>" in res.text


@pytest.mark.asyncio
async def test_shared_page_loads_the_bundled_font_through_its_token(env):
    client, _docs = env
    link = await _create(client, "team/plan.md")
    async with client(REMOTE) as c:
        page = await c.get(f"/share/{link['token']}")
        font = await c.get(f"/share/{link['token']}/font")
    assert f"url('{link['token']}/font')" in page.text
    assert "font-src 'self'" in page.headers["content-security-policy"]
    assert font.status_code == 200
    assert font.headers["content-type"] == "font/woff2"
    assert font.content[:4] == b"wOF2"
    assert "immutable" in font.headers["cache-control"]


@pytest.mark.asyncio
async def test_font_route_needs_a_live_token(env):
    client, _docs = env
    link = await _create(client, "team/plan.md")
    async with client(LOCAL) as c:
        await c.delete(f"/api/v1/shares/{link['id']}")
    async with client(REMOTE) as c:
        revoked = await c.get(f"/share/{link['token']}/font")
        bogus = await c.get("/share/nope/font")
        nested = await c.get(f"/share/{link['token']}/font/extra")
    assert revoked.status_code == 404
    assert bogus.status_code == 404
    assert nested.status_code == 404
