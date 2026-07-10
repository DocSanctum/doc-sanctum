import asyncio
import functools
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import async_session_factory, get_session, get_setting, set_setting
from ..models.source import Source, SourceIcon, SourceType
from ..services.poller import poll_now
from ..services.watcher import register_index_listener, start_watching, stop_watching
from ..vectorstore.indexer import (
    EngineUnavailableError,
    create_index,
    delete_source_index,
    handle_watch_event,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sources"])

# backend/sample-docs, baked into the image (prod) or bind-mounted with the
# rest of backend/ (dev) — see backend/Dockerfile and docker-compose.override.yml.
_SAMPLE_DOCS_PATH = Path(__file__).resolve().parents[2] / "sample-docs"
_SAMPLE_SOURCE_SEEDED_KEY = "sample_source_seeded"

_DEFAULT_POLL: dict[str, int] = {
    "github": 600,
    "gitlab": 600,
    "http": 300,
    "localhost": 300,
}

# The generic index.json-manifest source types require the doc server
# operator to hand-author and keep a manifest file in sync with every file
# change, which turned out to be too much upkeep in practice. Disabled until
# a lower-friction replacement (e.g. more git-hosting providers) ships.
_DISABLED_SOURCE_TYPES = {"http", "localhost"}


class RegisterSourceRequest(BaseModel):
    name: str | None = None
    type: SourceType
    path: str
    polling_interval_seconds: int | None = None
    icon: SourceIcon | None = None


class PatchSourceRequest(BaseModel):
    name: str | None = None
    polling_interval_seconds: int | None = None
    icon: SourceIcon | None = None


def _reject_local_source_in_scaleout(source_type: str) -> None:
    """scaleout backend replicas have no access to the operator's local
    filesystem, so local source registration must fail fast here rather than
    succeeding and later failing on every list/read/index attempt (FR-004,
    SC-003, specs/004-scaleout-deployment)."""
    if settings.deployment_mode == "scaleout" and source_type == "local":
        raise HTTPException(
            status_code=422,
            detail="Local sources are not supported in scaleout deployment mode",
        )


def _reject_disabled_source_type(source_type: str) -> None:
    if source_type in _DISABLED_SOURCE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Source type '{source_type}' is currently disabled",
        )


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


async def _finish_remote_registration(source: Source) -> None:
    """Build the initial vector index for a newly registered remote source in
    the background (FR-011) so POST /sources can respond immediately instead
    of blocking on a full-repo crawl + embed, which for a large GitHub repo
    could take minutes with no progress feedback to the caller. Mirrors the
    status handling already used by refresh_source/poll_now."""
    try:
        warnings = await create_index(source)
        status, error_msg = "active", None
        if warnings:
            logger.warning(
                "Initial index for source %s completed with %d warning(s)",
                source.id,
                len(warnings),
            )
    except Exception as exc:
        logger.exception("Failed to build initial index for source %s", source.id)
        status, error_msg = "error", str(exc)

    async with async_session_factory() as session:
        await session.execute(
            text("UPDATE source SET status = :s, error_message = :e WHERE id = :id"),
            {"s": status, "e": error_msg, "id": source.id},
        )
        await session.commit()


async def _resume_local_source(source: Source) -> None:
    """Restore a single local source's file watcher and rebuild its vector
    index in the background at startup. Both live only in process memory
    (the watcher registry in watcher.py, the vector store as chromadb's
    EphemeralClient) and are silently wiped on every backend restart, even
    though the source's DB row still says "active" — without this,
    semantic search over local sources would return nothing until the
    source was deleted and re-registered."""
    watch_root = os.path.expanduser(source.path)
    start_watching(source.id, watch_root)
    register_index_listener(
        source.id, functools.partial(handle_watch_event, source, watch_root)
    )

    async with async_session_factory() as session:
        await session.execute(
            text("UPDATE source SET status = 'syncing' WHERE id = :id"),
            {"id": source.id},
        )
        await session.commit()

    try:
        warnings = await create_index(source)
        status, error_msg = "active", None
        if warnings:
            logger.warning(
                "Startup reindex for source %s completed with %d warning(s)",
                source.id,
                len(warnings),
            )
    except Exception as exc:
        logger.exception("Failed to rebuild index for source %s at startup", source.id)
        status, error_msg = "error", str(exc)

    async with async_session_factory() as session:
        await session.execute(
            text("UPDATE source SET status = :s, error_message = :e WHERE id = :id"),
            {"s": status, "e": error_msg, "id": source.id},
        )
        await session.commit()


async def resume_local_sources() -> None:
    """Called once at app startup (main.py lifespan) to restore every
    registered local source's watcher and vector index. Each source's
    reindex runs as its own background task so a large vault doesn't delay
    app startup / health checks."""
    async with async_session_factory() as session:
        rows = (
            (await session.execute(text("SELECT * FROM source WHERE type = 'local'")))
            .mappings()
            .all()
        )
    for row in rows:
        asyncio.create_task(_resume_local_source(Source.from_row(dict(row))))


async def seed_sample_source() -> None:
    """Called once at app startup (main.py lifespan), after
    resume_local_sources(). On a brand-new install (no sources registered
    yet) this registers the bundled sample-docs/ folder as a local source so
    first-run users land on a working example instead of an empty tree. Gated
    by the `sample_source_seeded` setting so it only ever runs once per
    database — deleting the sample source later doesn't bring it back."""
    if await get_setting(_SAMPLE_SOURCE_SEEDED_KEY) is not None:
        return
    await set_setting(_SAMPLE_SOURCE_SEEDED_KEY, "true")

    if settings.deployment_mode == "scaleout" or not _SAMPLE_DOCS_PATH.is_dir():
        return

    async with async_session_factory() as session:
        source_count = (
            await session.execute(text("SELECT COUNT(*) FROM source"))
        ).scalar_one()
    if source_count:
        return

    source = Source(
        name="Sample Docs", type="local", path=str(_SAMPLE_DOCS_PATH), icon="📚"
    )
    try:
        await create_index(source)
    except EngineUnavailableError:
        logger.warning("Skipped seeding sample source: vector store unavailable")
        return

    async with async_session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO source (id,name,type,path,polling_interval_seconds,created_at,status,error_message,icon)"
                " VALUES (:id,:name,:type,:path,:poll,:created_at,:status,:err,:icon)"
            ),
            {**source.to_dict(), "poll": None, "err": None},
        )
        await session.commit()

    watch_root = os.path.expanduser(source.path)
    start_watching(source.id, watch_root)
    register_index_listener(
        source.id, functools.partial(handle_watch_event, source, watch_root)
    )


@router.post("/sources", status_code=201)
async def register_source(
    req: RegisterSourceRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    _reject_local_source_in_scaleout(req.type)
    _reject_disabled_source_type(req.type)
    name = req.name or req.path.rstrip("/").split("/")[-1]
    poll = req.polling_interval_seconds or _DEFAULT_POLL.get(req.type)
    is_local = req.type == "local"
    source = Source(
        name=name,
        type=req.type,
        path=req.path,
        polling_interval_seconds=poll,
        status="active" if is_local else "syncing",
        icon=req.icon,
    )

    index_warnings: list[dict] | None = None
    if is_local:
        # Local sources read straight from disk (no network round-trips), so
        # indexing them synchronously is cheap enough to keep failing fast
        # and clean, before anything is persisted.
        try:
            index_warnings = await create_index(source)
        except EngineUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        await session.execute(
            text(
                "INSERT INTO source (id,name,type,path,polling_interval_seconds,created_at,status,error_message,icon)"
                " VALUES (:id,:name,:type,:path,:poll,:created_at,:status,:err,:icon)"
            ),
            {**source.to_dict(), "poll": poll, "err": None},
        )
        await session.commit()
    except Exception as exc:
        if is_local:
            await delete_source_index(source.id)
        if "UNIQUE" in str(exc):
            raise HTTPException(status_code=409, detail="Path already registered")
        raise

    if is_local:
        watch_root = os.path.expanduser(source.path)
        start_watching(source.id, watch_root)
        register_index_listener(
            source.id, functools.partial(handle_watch_event, source, watch_root)
        )
    else:
        asyncio.create_task(_finish_remote_registration(source))

    result = source.to_dict()
    if index_warnings:
        result["index_warnings"] = index_warnings
    return result


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
    await delete_source_index(source_id)
    stop_watching(source_id)


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
    if "icon" in req.model_fields_set:
        updates["icon"] = req.icon
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
