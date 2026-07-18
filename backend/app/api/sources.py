import asyncio
import functools
import logging
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.crypto import encrypt_token
from ..core.database import async_session_factory, get_session, get_setting, set_setting
from ..models.source import Source, SourceIcon, SourceType
from ..services.poller import poll_now
from ..services.watcher import register_index_listener, start_watching, stop_watching
from ..vectorstore.indexer import (
    EngineUnavailableError,
    create_index,
    delete_source_index,
    handle_watch_event,
    summarize_index_warnings,
    sync_source_index,
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

# The backend always runs inside a Linux container, regardless of the host
# OS, so a Windows-style absolute path pasted straight from Explorer (e.g.
# `C:\Users\alice\docs`) is never valid as-is: no leading `/` makes it look
# relative, and its backslashes aren't path separators on Linux. WSL2 exposes
# each Windows drive under /mnt/<lowercase drive letter>/..., which is also
# where a container running under Docker Desktop's WSL2 integration can see
# it (given the matching bind mount) — so translate to that form instead of
# letting it fail confusingly downstream.
_WINDOWS_ABS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _normalize_local_path(path: str) -> str:
    match = _WINDOWS_ABS_PATH_RE.match(path)
    if not match:
        return os.path.expanduser(path)
    drive = path[0].lower()
    rest = path[2:].replace("\\", "/").lstrip("/")
    return f"/mnt/{drive}/{rest}"


class RegisterSourceRequest(BaseModel):
    name: str | None = None
    type: SourceType
    path: str
    polling_interval_seconds: int | None = None
    icon: SourceIcon | None = None
    # Optional per-source PAT (specs/007-source-access-token). Only
    # meaningful for github/gitlab; ignored for other source types.
    access_token: str | None = None


class PatchSourceRequest(BaseModel):
    name: str | None = None
    polling_interval_seconds: int | None = None
    icon: SourceIcon | None = None
    # Omitted entirely -> keep existing token. Non-empty string -> replace
    # (re-encrypt). Empty string "" -> delete (falls back to global .env
    # token). Only meaningful for github/gitlab sources.
    access_token: str | None = None


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
        status, error_msg = summarize_index_warnings(warnings)
        if warnings:
            logger.warning(
                "Initial index for source %s completed with %d warning(s) -> %s",
                source.id,
                len(warnings),
                status,
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
    """Restore a single local source's file watcher at startup (the watcher
    registry in watcher.py lives only in process memory and is wiped on
    every backend restart) and bring its vector index up to date.

    The vector index and its change-tracking cache now persist across
    restarts, so this runs the same incremental sync_source_index() the
    poller uses instead of forcing a
    full re-embed of every document — an unchanged source's restart is a
    fast no-op diff rather than a full rebuild. A source with no prior
    persisted state (first-ever run) is naturally handled the same way:
    sync_source_index() treats every document as new when the cache is
    empty, which is equivalent to a full build."""
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
        warnings = await sync_source_index(source)
        status, error_msg = "active", None
        if warnings:
            logger.warning(
                "Startup sync for source %s completed with %d warning(s)",
                source.id,
                len(warnings),
            )
    except Exception as exc:
        logger.exception("Failed to sync index for source %s at startup", source.id)
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
    is_local = req.type == "local"
    path = _normalize_local_path(req.path) if is_local else req.path
    if is_local and not os.path.isdir(path):
        raise HTTPException(
            status_code=422,
            detail=f"Path not found or not a directory (inside the backend container): {path}",
        )
    name = req.name or path.rstrip("/").split("/")[-1]
    poll = req.polling_interval_seconds or _DEFAULT_POLL.get(req.type)
    access_token_encrypted = (
        encrypt_token(req.access_token)
        if req.access_token and req.type in ("github", "gitlab")
        else None
    )
    source = Source(
        name=name,
        type=req.type,
        path=path,
        polling_interval_seconds=poll,
        status="active" if is_local else "syncing",
        icon=req.icon,
        access_token_encrypted=access_token_encrypted,
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
                "INSERT INTO source (id,name,type,path,polling_interval_seconds,created_at,status,error_message,icon,access_token_encrypted)"
                " VALUES (:id,:name,:type,:path,:poll,:created_at,:status,:err,:icon,:access_token_encrypted)"
            ),
            {
                **source.to_dict(),
                "poll": poll,
                "err": None,
                "access_token_encrypted": source.access_token_encrypted,
            },
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
    # Routed through Source.to_dict() (not a raw dict(row)) so
    # access_token_encrypted never reaches this response — only the derived
    # access_token_configured boolean does (FR-004, FR-009).
    return [Source.from_row(dict(r)).to_dict() for r in rows]


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
    source = await _get_or_404(session, source_id)
    updates: dict = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.polling_interval_seconds is not None:
        updates["polling_interval_seconds"] = req.polling_interval_seconds
    if "icon" in req.model_fields_set:
        updates["icon"] = req.icon
    if "access_token" in req.model_fields_set and source.type in ("github", "gitlab"):
        updates["access_token_encrypted"] = (
            encrypt_token(req.access_token) if req.access_token else None
        )
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
