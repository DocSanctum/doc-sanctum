from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .tools.list_documents import list_documents_handler
from .tools.read_document import read_document_handler
from .tools.search_documents import search_documents_handler
from .tools.semantic_search_documents import semantic_search_documents_handler

mcp = FastMCP(
    "doc-sanctum",
    # FastMCP defaults this to "/mcp", which combined with the app's own
    # mount point in main.py would produce a doubled path. Collapse it to
    # the mount root so the streamable-http transport is reachable at
    # exactly the mount path (see main.py's app.mount("/mcp", ...)).
    streamable_http_path="/",
    # FastMCP's own default here (DNS-rebinding protection with an empty
    # allowed_origins list) rejects every request that carries an Origin
    # header at all, independently of main.py's CORS config — it's a
    # separate check inside the MCP SDK's transport layer, not something
    # CORSMiddleware can reach. This mount has no cookies/credentials, so
    # it's gated the same way CORS is: open to any client origin.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

mcp.tool(name="list_documents")(list_documents_handler)
mcp.tool(name="read_document")(read_document_handler)
mcp.tool(name="search_documents")(search_documents_handler)
mcp.tool(name="semantic_search_documents")(semantic_search_documents_handler)
