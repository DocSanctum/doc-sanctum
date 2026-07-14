from fastapi import APIRouter
from pydantic import BaseModel

from ..core.database import get_setting, set_setting

router = APIRouter(prefix="/mcp", tags=["mcp"])

SETTING_KEY = "mcp_enabled"

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
    tools: list[dict]


class McpPatch(BaseModel):
    enabled: bool


@router.get("/status", response_model=McpStatus)
async def get_mcp_status():
    return McpStatus(
        enabled=await is_enabled(),
        sse_url="/mcp-sse/sse",
        http_url="/mcp",
        tools=TOOLS,
    )


@router.patch("/status", response_model=McpStatus)
async def patch_mcp_status(body: McpPatch):
    await set_setting(SETTING_KEY, "true" if body.enabled else "false")
    return McpStatus(
        enabled=body.enabled, sse_url="/mcp-sse/sse", http_url="/mcp", tools=TOOLS
    )
