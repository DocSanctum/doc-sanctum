from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .api import deployment, files, locale, search, sources, sse
from .api import mcp as mcp_api
from .api.sources import resume_local_sources
from .core.database import create_tables
from .mcp.server import mcp
from .services.poller import start_polling_all
from .vectorstore.client import init_engine

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    init_engine()
    await resume_local_sources()
    await start_polling_all()
    yield


app = FastAPI(title="DocSanctum", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(sse.router, prefix="/api/v1")
app.include_router(mcp_api.router, prefix="/api/v1")
app.include_router(deployment.router, prefix="/api/v1")
app.include_router(locale.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")

app.mount("/mcp", _make_guard(_mcp_sse_app))  # SSE transport (legacy)
app.mount(
    "/mcp-http", _make_guard(_mcp_http_app)
)  # Streamable HTTP transport (MCP 1.x)
