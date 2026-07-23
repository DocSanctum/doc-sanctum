import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .api import deployment, files, locale, search, sources, sse
from .api import mcp as mcp_api
from .api.sources import resume_local_sources, seed_sample_source
from .core.crypto import ensure_master_key
from .core.database import create_tables
from .mcp.server import mcp
from .services.poller import start_polling_all
from .vectorstore.client import init_engine, is_engine_available, reconnect_loop
from .vectorstore.rebuild_check import check_and_recover

_mcp_sse_app: ASGIApp = mcp.sse_app()
_mcp_http_app: ASGIApp = mcp.streamable_http_app()


def _make_guard(inner: ASGIApp) -> ASGIApp:
    async def guard(scope: Scope, receive: Receive, send: Send) -> None:
        if not await mcp_api.is_enabled():
            response = JSONResponse(
                {"detail": "MCP server is disabled"}, status_code=503
            )
            await response(scope, receive, send)
            return
        await inner(scope, receive, send)

    return guard


_MCP_MOUNT_PATHS = ("/mcp", "/mcp-sse")


class _NormalizeMcpMountPath:
    # Starlette's Mount only matches "<mount>/..." (it requires a trailing
    # slash before any sub-path), so a bare "/mcp" or "/mcp-sse" request
    # never matches the Mount and instead falls through to the router's
    # redirect_slashes fallback, which 307s to the slashed path. Not every
    # MCP client follows redirects on POST, so rewrite the path here, before
    # it reaches the router, instead of relying on a round trip.
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] in _MCP_MOUNT_PATHS:
            scope = dict(scope)
            scope["path"] += "/"
        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    ensure_master_key()
    init_engine()
    if not is_engine_available():
        # Keeps retrying at a relaxed interval in the background, so the app
        # recovers on its own once the vector store becomes reachable
        # instead of needing a full backend restart.
        asyncio.create_task(reconnect_loop())
    # Must run before resume_local_sources()/start_polling_all() so any
    # cache invalidation below (embedding model change, incomplete prior
    # write) is picked up by each source's very first post-restart sync.
    await check_and_recover()
    await resume_local_sources()
    await seed_sample_source()
    await start_polling_all()
    # Starlette never forwards the "lifespan" scope to mounted sub-apps, so
    # streamable_http_app()'s own lifespan (which starts this) never runs on
    # its own; without it every /mcp request fails with
    # "Task group is not initialized. Make sure to use run()."
    async with mcp.session_manager.run():
        yield


class _McpAwareCors:
    # External MCP clients (the Obsidian plugin, or any other MCP client
    # that happens to run inside a browser-like renderer) are subject to
    # CORS just like a website, but unlike our own bundled frontend there's
    # no fixed set of client origins to allowlist ahead of time. The /mcp
    # and /mcp-sse mounts carry no cookies/credentials, so reflecting back
    # whatever origin asks is no more exposed than the mount already is to
    # plain (non-browser) HTTP clients — CORS only ever gated browser-JS
    # access here. Everything else keeps the narrow frontend-only allowlist.
    def __init__(self, app: ASGIApp) -> None:
        self._narrow = CORSMiddleware(
            app,
            allow_origins=["http://localhost:3000", "http://localhost:5173"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._permissive = CORSMiddleware(
            app,
            allow_origin_regex=".*",
            allow_methods=["*"],
            allow_headers=["*"],
            # Without this, browser-based clients can't read the
            # Mcp-Session-Id response header from JS (CORS hides
            # non-safelisted response headers by default), so they send
            # every request after initialize with no session ID and the
            # MCP session manager rejects them.
            expose_headers=["*"],
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith("/mcp"):
            await self._permissive(scope, receive, send)
        else:
            await self._narrow(scope, receive, send)


app = FastAPI(title="DocSanctum", lifespan=lifespan)

app.add_middleware(_McpAwareCors)
app.add_middleware(_NormalizeMcpMountPath)

app.include_router(sources.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(sse.router, prefix="/api/v1")
app.include_router(mcp_api.router, prefix="/api/v1")
app.include_router(deployment.router, prefix="/api/v1")
app.include_router(locale.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")

app.mount("/mcp-sse", _make_guard(_mcp_sse_app))  # SSE transport (legacy)
app.mount(
    "/mcp", _make_guard(_mcp_http_app)
)  # Streamable HTTP transport (MCP 1.x, recommended)
