"""Remote MCP listener: a second backend socket that serves only the MCP
mounts and requires a bearer token.

The main listener stays loopback-only and unauthenticated, so the web UI and
local MCP clients keep working as before. The remote listener is what gets
published to the LAN, and because it rejects every non-MCP path, other
machines can query documents but can never reach the REST API (source
registration, file reads, settings). It also serves view-only share links.
"""

from __future__ import annotations

import hmac
import secrets
from collections.abc import Sequence

from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import HTMLResponse, JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ..services.share_i18n import pick_locale, t
from ..services.share_render import SECURITY_HEADERS, render_notice_page
from .database import async_session_factory, set_setting

TOKEN_SETTING_KEY = "remote_mcp_token"
_MCP_PREFIXES = ("/mcp", "/mcp-sse")


def _new_token() -> str:
    return secrets.token_urlsafe(32)


async def get_or_create_token() -> str:
    # INSERT OR IGNORE keeps the first token when several scaleout replicas
    # boot at once against the same shared SQLite database.
    async with async_session_factory() as session:
        await session.execute(
            text("INSERT OR IGNORE INTO setting(key, value) VALUES(:k, :v)"),
            {"k": TOKEN_SETTING_KEY, "v": _new_token()},
        )
        await session.commit()
        row = await session.execute(
            text("SELECT value FROM setting WHERE key = :k"), {"k": TOKEN_SETTING_KEY}
        )
        return str(row.scalar_one())


async def regenerate_token() -> str:
    token = _new_token()
    await set_setting(TOKEN_SETTING_KEY, token)
    return token


def _is_mcp_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _MCP_PREFIXES)


def _is_share_path(path: str) -> bool:
    # Only "/share/<token>" and its asset, font and diagram script routes
    # pass, so no other route can hide under the share prefix.
    rest = path.removeprefix("/share/")
    if rest == path:
        return False
    token, sep, sub = rest.partition("/")
    return bool(token) and (not sep or sub in ("asset", "font", "mermaid.js"))


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope["headers"]:
        if key == name:
            return value.decode("latin-1")
    return None


def _bearer_token(scope: Scope) -> str | None:
    value = _header(scope, b"authorization")
    if value is None:
        return None
    scheme, _, credentials = value.partition(" ")
    if scheme.lower() == "bearer" and credentials:
        return credentials.strip()
    return None


class ListenerGuard:
    """Routes each request by the socket it arrived on: the remote MCP port
    gets the path and token checks, every other port gets the Host allowlist
    that blocks DNS rebinding."""

    def __init__(
        self, app: ASGIApp, allowed_hosts: Sequence[str], remote_port: int
    ) -> None:
        self._app = app
        self._trusted = TrustedHostMiddleware(app, allowed_hosts=allowed_hosts)
        self._remote_port = remote_port

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return
        server = scope.get("server")
        if not server or server[1] != self._remote_port:
            await self._trusted(scope, receive, send)
            return

        # A share link carries its own token in the path and is checked by
        # the viewer route, so it skips the MCP bearer token.
        if _is_share_path(scope["path"]):
            await self._app(scope, receive, send)
            return
        # Someone who types just the host and port sees a hint, not bare JSON.
        if scope["type"] == "http" and scope["path"] == "/":
            locale = pick_locale(_header(scope, b"accept-language"))
            page = render_notice_page(t(locale, "root"), locale)
            await HTMLResponse(page, headers=SECURITY_HEADERS)(scope, receive, send)
            return
        # The token stands in for the Host check here, since a DNS rebinding
        # page cannot know it, so LAN clients may use any hostname or IP.
        if not _is_mcp_path(scope["path"]):
            await JSONResponse({"detail": "Not Found"}, status_code=404)(
                scope, receive, send
            )
            return
        presented = _bearer_token(scope)
        expected = await get_or_create_token()
        if presented is None or not hmac.compare_digest(presented, expected):
            await JSONResponse(
                {"detail": "Missing or invalid bearer token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )(scope, receive, send)
            return
        await self._app(scope, receive, send)
