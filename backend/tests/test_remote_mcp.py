from __future__ import annotations

import backend.app.core.remote_mcp as remote_mcp_module
import httpx
import pytest
from backend.app.core.remote_mcp import ListenerGuard

TOKEN = "s3cret-token"
REMOTE_PORT = 8100


async def _inner(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"inner"})


@pytest.fixture
def client(monkeypatch):
    async def fake_token() -> str:
        return TOKEN

    monkeypatch.setattr(remote_mcp_module, "get_or_create_token", fake_token)
    guard = ListenerGuard(_inner, allowed_hosts=["localhost"], remote_port=REMOTE_PORT)
    transport = httpx.ASGITransport(app=guard)
    return lambda base: httpx.AsyncClient(transport=transport, base_url=base)


@pytest.mark.asyncio
async def test_remote_port_requires_bearer_token(client):
    async with client("http://192.168.1.10:8100") as c:
        missing = await c.post("/mcp")
        wrong = await c.post("/mcp", headers={"Authorization": "Bearer nope"})
        ok = await c.post("/mcp", headers={"Authorization": f"Bearer {TOKEN}"})
    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert wrong.status_code == 401
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_remote_port_never_serves_the_rest_api(client):
    """Even with a valid token, the remote listener must not expose source
    registration, file reads or settings."""
    headers = {"Authorization": f"Bearer {TOKEN}"}
    async with client("http://192.168.1.10:8100") as c:
        api = await c.post("/api/v1/sources", headers=headers)
        lookalike = await c.get("/mcpx", headers=headers)
        sse = await c.get("/mcp-sse/sse", headers=headers)
    assert api.status_code == 404
    assert lookalike.status_code == 404
    assert sse.status_code == 200


@pytest.mark.asyncio
async def test_remote_port_errors_are_readable_by_browser_clients(monkeypatch):
    """A 401 without CORS headers reaches a browser client (e.g. the Obsidian
    plugin) as an opaque network error, so it could never tell a bad token
    apart from an unreachable server. Preflights must also pass untouched."""
    from backend.app.main import app

    async def fake_token() -> str:
        return TOKEN

    monkeypatch.setattr(remote_mcp_module, "get_or_create_token", fake_token)
    origin = {"Origin": "app://obsidian.md"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://192.168.1.10:8100"
    ) as c:
        rejected = await c.post("/mcp", headers=origin)
        preflight = await c.options(
            "/mcp",
            headers={
                **origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization",
            },
        )
    assert rejected.status_code == 401
    assert rejected.headers["access-control-allow-origin"] == "app://obsidian.md"
    assert preflight.status_code == 200
    assert "authorization" in preflight.headers["access-control-allow-headers"]


@pytest.mark.asyncio
async def test_main_port_keeps_host_allowlist_and_needs_no_token(client):
    async with client("http://localhost:8000") as c:
        local = await c.post("/mcp")
    async with client("http://192.168.1.10:8000") as c:
        foreign = await c.post("/mcp")
    assert local.status_code == 200
    assert foreign.status_code == 400
