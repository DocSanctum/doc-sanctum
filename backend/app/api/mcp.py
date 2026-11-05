import os

from fastapi import APIRouter
from pydantic import BaseModel

from ..core.database import get_setting, set_setting
from ..core.remote_mcp import get_or_create_token, regenerate_token

router = APIRouter(prefix="/mcp", tags=["mcp"])

SETTING_KEY = "mcp_enabled"


# The container has no way to know how docker-compose actually published its
# port to the host (BACKEND_PORT is a range; --scale/prior conflicts can
# shift the real mapping higher) — this only reports the operator's
# configured starting port, which is correct for the common single-replica
# case and is still far better than a hardcoded guess.
def _host_port() -> int:
    return int(os.environ.get("BACKEND_PORT", "8000"))


# Like BACKEND_PORT, these echo how compose publishes the remote MCP listener.
# A loopback bind address means other machines cannot reach it yet.
def _remote_port() -> int:
    return int(os.environ.get("REMOTE_MCP_PORT", "8020"))


def _remote_reachable() -> bool:
    bind = os.environ.get("REMOTE_MCP_BIND_ADDRESS", "127.0.0.1")
    return not bind.startswith("127.") and bind not in ("localhost", "::1")


TOOLS = [
    {
        "name": "list_documents",
        "description": "List all indexed documents across sources",
    },
    {"name": "read_document", "description": "Read the content of a specific document"},
    {"name": "search_documents", "description": "Search documents by keyword"},
    {
        "name": "semantic_search_documents",
        "description": "Search documents by semantic meaning using a natural-language query",
    },
]


async def is_enabled() -> bool:
    value = await get_setting(SETTING_KEY, default="true")
    return value == "true"


class McpStatus(BaseModel):
    enabled: bool
    sse_url: str
    http_url: str
    host_port: int
    tools: list[dict]
    remote_port: int
    remote_reachable: bool
    # Served only on the loopback-bound main listener, which the remote MCP
    # listener never routes /api requests to.
    remote_token: str


class McpPatch(BaseModel):
    enabled: bool


async def _status(enabled: bool) -> McpStatus:
    return McpStatus(
        enabled=enabled,
        sse_url="/mcp-sse/sse",
        http_url="/mcp",
        host_port=_host_port(),
        tools=TOOLS,
        remote_port=_remote_port(),
        remote_reachable=_remote_reachable(),
        remote_token=await get_or_create_token(),
    )


@router.get("/status", response_model=McpStatus)
async def get_mcp_status():
    return await _status(await is_enabled())


@router.patch("/status", response_model=McpStatus)
async def patch_mcp_status(body: McpPatch):
    await set_setting(SETTING_KEY, "true" if body.enabled else "false")
    return await _status(body.enabled)


@router.post("/remote-token", response_model=McpStatus)
async def rotate_remote_token():
    """Replace the remote MCP bearer token, which immediately locks out every
    remote client still using the old one."""
    await regenerate_token()
    return await _status(await is_enabled())
