import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..models.source import Source, SourceType
from ..services.poller import poll_now

router = APIRouter(tags=["sources"])

_DEFAULT_POLL: dict[str, int] = {"github": 600, "http": 300, "localhost": 300}


class RegisterSourceRequest(BaseModel):
    name: str | None = None
    type: SourceType
    path: str
    polling_interval_seconds: int | None = None


class PatchSourceRequest(BaseModel):
    name: str | None = None
    polling_interval_seconds: int | None = None


async def _get_or_404(session: AsyncSession, source_id: str) -> Source:
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


@router.post("/sources", status_code=201)
async def register_source(
    req: RegisterSourceRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    name = req.name or req.path.rstrip("/").split("/")[-1]
    poll = req.polling_interval_seconds or _DEFAULT_POLL.get(req.type)
    source = Source(
        name=name, type=req.type, path=req.path, polling_interval_seconds=poll
    )
    try:
        await session.execute(
            text(
                "INSERT INTO source (id,name,type,path,polling_interval_seconds,created_at,status,error_message)"
                " VALUES (:id,:name,:type,:path,:poll,:created_at,:status,:err)"
            ),
            {**source.to_dict(), "poll": poll, "err": None},
        )
        await session.commit()
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise HTTPException(status_code=409, detail="Path already registered")
        raise
    return source.to_dict()


@router.get("/sources")
async def list_sources(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (
        (await session.execute(text("SELECT * FROM source ORDER BY created_at")))
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: str, session: AsyncSession = Depends(get_session)
) -> None:
    await _get_or_404(session, source_id)
    await session.execute(text("DELETE FROM source WHERE id = :id"), {"id": source_id})
    await session.commit()


@router.patch("/sources/{source_id}")
async def patch_source(
    source_id: str,
    req: PatchSourceRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _get_or_404(session, source_id)
    updates: dict = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.polling_interval_seconds is not None:
        updates["polling_interval_seconds"] = req.polling_interval_seconds
    if updates:
        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        await session.execute(
            text(f"UPDATE source SET {set_clause} WHERE id = :id"),
            {**updates, "id": source_id},
        )
        await session.commit()
    return (await _get_or_404(session, source_id)).to_dict()


@router.post("/sources/{source_id}/refresh", status_code=202)
async def refresh_source(
    source_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    source = await _get_or_404(session, source_id)
    if source.type == "local":
        raise HTTPException(
            status_code=400, detail="Local sources do not need manual refresh"
        )
    await session.execute(
        text("UPDATE source SET status = 'syncing' WHERE id = :id"), {"id": source_id}
    )
    await session.commit()
    asyncio.create_task(poll_now(source))
    return {"detail": "Refresh queued"}
