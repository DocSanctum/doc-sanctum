import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..mcp.cache import get_cached
from ..mcp.tools.list_documents import _get_tree_with_cache
from ..mcp.tools.read_document import read_with_cache
from ..models.source import Source

router = APIRouter(tags=["files"])


async def _get_source_or_404(session: AsyncSession, source_id: str) -> Source:
    row = (
        (
            await session.execute(
                text("SELECT * FROM source WHERE id = :id"), {"id": source_id}
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")
    return Source.from_row(dict(row))


@router.get("/sources/{source_id}/tree")
async def get_tree(
    source_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    source = await _get_source_or_404(session, source_id)
    if source.status == "error":
        # A transient failure (e.g. one flaky page in a large paginated
        # traversal) flips the source to "error", but a tree from an
        # earlier successful poll may still be cached — serve that instead
        # of a hard failure.
        cached = get_cached(source_id, ignore_ttl=True)
        if cached is not None:
            return cached["data"]
        raise HTTPException(
            status_code=503, detail=source.error_message or "Source error"
        )
    tree, _warning = await _get_tree_with_cache(source)
    return tree


@router.get("/sources/{source_id}/file", response_class=PlainTextResponse)
async def get_file(
    source_id: str,
    path: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> str:
    source = await _get_source_or_404(session, source_id)

    if source.type != "local":
        # github/http/localhost sources have no local file to stat — fetch
        # (and cache) the content over the network instead (previously this
        # endpoint only handled "local" and always 404'd for remote sources).
        try:
            content, _warning = await read_with_cache(source, path)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise HTTPException(
                status_code=502, detail=f"Failed to fetch file from source: {exc}"
            ) from exc
        return content

    # Path traversal guard
    expanded = os.path.expanduser(source.path)
    safe_root = os.path.realpath(expanded)
    target = os.path.realpath(os.path.join(expanded, path))
    if not target.startswith(safe_root + os.sep) and target != safe_root:
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="File not found")
    with open(target, encoding="utf-8") as f:
        return f.read()
