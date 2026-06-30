from mcp.server.fastmcp import FastMCP

from .tools.list_documents import list_documents_handler
from .tools.read_document import read_document_handler
from .tools.search_documents import search_documents_handler

mcp = FastMCP("doc-sanctum")

mcp.tool(name="list_documents")(list_documents_handler)
mcp.tool(name="read_document")(read_document_handler)
mcp.tool(name="search_documents")(search_documents_handler)
