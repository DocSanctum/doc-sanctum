import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..models.source import Source
from ..services.tree_builder import build_local_tree, build_remote_tree

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
        raise HTTPException(
            status_code=503, detail=source.error_message or "Source error"
        )
    if source.type == "local":
        return build_local_tree(source)
    return await build_remote_tree(source)


@router.get("/sources/{source_id}/file", response_class=PlainTextResponse)
async def get_file(
    source_id: str,
    path: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> str:
    source = await _get_source_or_404(session, source_id)
    # Path traversal guard
    safe_root = os.path.realpath(source.path)
    target = os.path.realpath(os.path.join(source.path, path))
    if not target.startswith(safe_root + os.sep) and target != safe_root:
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="File not found")
    with open(target, encoding="utf-8") as f:
        return f.read()
