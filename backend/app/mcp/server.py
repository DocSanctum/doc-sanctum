from mcp.server.fastmcp import FastMCP

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
)

mcp.tool(name="list_documents")(list_documents_handler)
mcp.tool(name="read_document")(read_document_handler)
mcp.tool(name="search_documents")(search_documents_handler)
mcp.tool(name="semantic_search_documents")(semantic_search_documents_handler)
