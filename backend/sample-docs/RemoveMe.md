# Welcome to DocSanctum

This document was added automatically on your first run so you have something
to read before pointing DocSanctum at your own docs. It's registered as a
regular source named **Sample Docs** — once you've added a real source, open
**Settings → Sources** and delete it. Nothing else changes when you do.

## Table of contents

Every heading on this page shows up in the table of contents on the right,
and each one gets a stable permalink you can copy from its `#` anchor on
hover.

## Code blocks

Code blocks are syntax-highlighted and get a copy button in the top-right
corner on hover.

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

```bash
# Register a source from the CLI via the API instead of the UI
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{"type": "local", "path": "/home/me/notes"}'
```

## Tables

| Feature | Where to find it |
|---|---|
| Keyword search | Command palette (`Ctrl/Cmd+K`) |
| Semantic search | Search tab in the sidebar |
| Split view | Drag a tab to either edge of the reading pane |
| MCP tools | `list_documents`, `read_document`, `search_documents`, `semantic_search_documents` |

## Task lists

- [x] Clone the repo and run `./start.sh`
- [x] Open http://localhost:3000
- [ ] Add your first real source
- [ ] Delete this sample source

## Blockquotes and footnotes

> A single search box that actually finds things, across every source you
> register — that's the whole idea.

DocSanctum also exposes an MCP server[^mcp], so an AI assistant can answer
questions from your docs instead of guessing.

[^mcp]: Model Context Protocol — see the `/mcp` and `/mcp-http` endpoints in the backend.

## Abbreviations

DocSanctum's backend is built on FastAPI and speaks MCP to any client that supports it.

*[MCP]: Model Context Protocol
*[API]: Application Programming Interface
