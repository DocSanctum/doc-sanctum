"""View-only share links for single documents.

`router` is the management API, served only on the loopback main listener.
`viewer_router` serves `/share/<token>` and the images that document embeds,
which the LAN listener also exposes without a bearer token because the share
token itself is the credential.
"""

from __future__ import annotations

import os
import secrets
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import async_session_factory, get_session, get_setting, set_setting
from ..models.source import Source
from ..services.document_access import (
    flatten_tree,
    read_asset_with_cache,
    read_raw_with_cache,
)
from ..services.document_cache import get_cached
from ..services.document_formats import is_supported
from ..services.share_i18n import Locale, pick_locale, t
from ..services.share_render import (
    SECURITY_HEADERS,
    referenced_images,
    render_markdown_page,
    render_notice_page,
)
from .files import ASSET_HEADERS
from .mcp import _remote_port, _remote_reachable

router = APIRouter(prefix="/shares", tags=["shares"])
viewer_router = APIRouter(tags=["share-viewer"])

BASE_URL_SETTING_KEY = "share_base_url"


class ShareLink(BaseModel):
    id: str
    token: str
    source_id: str
    source_name: str | None
    path: str
    label: str | None
    created_at: str
    last_accessed_at: str | None
    access_count: int
    # None means "unknown": a remote source whose tree is not cached yet.
    available: bool | None


class CreateShareRequest(BaseModel):
    source_id: str
    path: str = Field(min_length=1)
    label: str | None = Field(default=None, max_length=200)


class ShareSettings(BaseModel):
    base_url: str
    # A best-effort default built from the host name start.sh passes in.
    suggested_base_url: str
    remote_port: int
    remote_reachable: bool


class ShareSettingsPatch(BaseModel):
    base_url: str = Field(max_length=500)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _suggested_base_url() -> str:
    host = os.environ.get("SHARE_HOST_HINT", "").strip()
    return f"http://{host}:{_remote_port()}" if host else ""


async def _settings() -> ShareSettings:
    return ShareSettings(
        base_url=await get_setting(BASE_URL_SETTING_KEY, default="") or "",
        suggested_base_url=_suggested_base_url(),
        remote_port=_remote_port(),
        remote_reachable=_remote_reachable(),
    )


def _is_available(source: Source, path: str) -> bool | None:
    if source.type == "local":
        root = os.path.realpath(os.path.expanduser(source.path))
        target = os.path.realpath(os.path.join(root, path))
        return target.startswith(root + os.sep) and os.path.isfile(target)
    cached = get_cached(source.id, ignore_ttl=True)
    if cached is None:
        return None
    files: list[dict[str, Any]] = []
    flatten_tree(cached["data"].get("root", {}), files, source)
    return any(f["path"] == path for f in files)


async def _load_source(session: AsyncSession, source_id: str) -> Source | None:
    row = (
        (
            await session.execute(
                text("SELECT * FROM source WHERE id = :id"), {"id": source_id}
            )
        )
        .mappings()
        .first()
    )
    return Source.from_row(dict(row)) if row else None


def _to_model(row: dict[str, Any], source: Source | None) -> ShareLink:
    return ShareLink(
        id=row["id"],
        token=row["token"],
        source_id=row["source_id"],
        source_name=source.name if source else None,
        path=row["path"],
        label=row["label"],
        created_at=row["created_at"],
        last_accessed_at=row["last_accessed_at"],
        access_count=row["access_count"],
        available=_is_available(source, row["path"]) if source else False,
    )


@router.get("", response_model=list[ShareLink])
async def list_shares(session: AsyncSession = Depends(get_session)):
    rows = (
        (
            await session.execute(
                text("SELECT * FROM share_link ORDER BY created_at DESC")
            )
        )
        .mappings()
        .all()
    )
    sources: dict[str, Source | None] = {}
    links = []
    for row in rows:
        sid = row["source_id"]
        if sid not in sources:
            sources[sid] = await _load_source(session, sid)
        links.append(_to_model(dict(row), sources[sid]))
    return links


@router.post("", response_model=ShareLink, status_code=201)
async def create_share(
    body: CreateShareRequest, session: AsyncSession = Depends(get_session)
):
    source = await _load_source(session, body.source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if not is_supported(body.path):
        raise HTTPException(status_code=422, detail="Unsupported document type")
    row = {
        "id": str(uuid.uuid4()),
        "token": secrets.token_urlsafe(24),
        "source_id": source.id,
        "path": body.path,
        "label": (body.label or "").strip() or None,
        "created_at": _now(),
        "last_accessed_at": None,
        "access_count": 0,
    }
    await session.execute(
        text(
            "INSERT INTO share_link(id, token, source_id, path, label, created_at) "
            "VALUES(:id, :token, :source_id, :path, :label, :created_at)"
        ),
        row,
    )
    await session.commit()
    return _to_model(row, source)


@router.delete("/{share_id}", status_code=204)
async def delete_share(share_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        text("DELETE FROM share_link WHERE id = :id"), {"id": share_id}
    )
    await session.commit()
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise HTTPException(status_code=404, detail="Share link not found")


@router.get("/settings", response_model=ShareSettings)
async def get_share_settings():
    return await _settings()


@router.put("/settings", response_model=ShareSettings)
async def put_share_settings(body: ShareSettingsPatch):
    await set_setting(BASE_URL_SETTING_KEY, body.base_url.strip().rstrip("/"))
    return await _settings()


def _locale(request: Request) -> Locale:
    return pick_locale(request.headers.get("accept-language"))


def _notice(locale: Locale, key: str, status_code: int) -> HTMLResponse:
    return HTMLResponse(
        render_notice_page(t(locale, key), locale),
        status_code=status_code,
        headers=SECURITY_HEADERS,
    )


async def _open_share(
    token: str, locale: Locale
) -> tuple[dict[str, Any], Source] | HTMLResponse:
    """Look up a live share link, or return the notice page explaining why not."""
    async with async_session_factory() as session:
        row = (
            (
                await session.execute(
                    text("SELECT * FROM share_link WHERE token = :t"), {"t": token}
                )
            )
            .mappings()
            .first()
        )
        source = await _load_source(session, row["source_id"]) if row else None
    if row is None or source is None:
        return _notice(locale, "invalid", 404)
    expires_at = row["expires_at"]
    if expires_at and expires_at <= _now():
        return _notice(locale, "expired", 410)
    return dict(row), source


def _share_asset_url(token: str) -> Callable[[str], str]:
    # Relative to /share/<token>, so it also works behind a path-prefixing proxy.
    return lambda path: f"{token}/asset?path={quote(path, safe='')}"


@viewer_router.get("/share/{token}", response_model=None)
async def view_share(token: str, request: Request) -> Response:
    locale = _locale(request)
    opened = await _open_share(token, locale)
    if isinstance(opened, Response):
        return opened
    row, source = opened

    path = row["path"]
    try:
        raw, _warning = await read_raw_with_cache(source, path)
    except ValueError:
        return _notice(locale, "gone", 404)
    except (httpx.HTTPStatusError, httpx.RequestError):
        return _notice(locale, "fetch_failed", 502)

    async with async_session_factory() as session:
        await session.execute(
            text(
                "UPDATE share_link SET access_count = access_count + 1, "
                "last_accessed_at = :now WHERE id = :id"
            ),
            {"now": _now(), "id": row["id"]},
        )
        await session.commit()

    if path.lower().endswith(".pdf"):
        name = quote(path.rsplit("/", 1)[-1], safe="")
        headers = {
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "Content-Disposition": f"inline; filename*=UTF-8''{name}",
        }
        return Response(content=raw, media_type="application/pdf", headers=headers)
    try:
        markdown = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _notice(locale, "decode_failed", 500)
    page = render_markdown_page(
        path,
        markdown,
        asset_url=_share_asset_url(token),
        font_url=f"{token}/font",
        locale=locale,
    )
    return HTMLResponse(page, headers=SECURITY_HEADERS)


@viewer_router.get("/share/{token}/asset", response_model=None)
async def view_share_asset(token: str, path: str, request: Request) -> Response:
    """Serve an image only if the shared document currently embeds it, so a
    token never exposes other files in the same source."""
    opened = await _open_share(token, _locale(request))
    if isinstance(opened, Response):
        return opened
    row, source = opened
    doc_path = row["path"]
    if not doc_path.lower().endswith(".md"):
        raise HTTPException(status_code=404, detail="Not Found")
    try:
        raw_doc, _warning = await read_raw_with_cache(source, doc_path)
        if path not in referenced_images(doc_path, raw_doc.decode("utf-8")):
            raise HTTPException(status_code=404, detail="Not Found")
        raw, media_type, _warning = await read_asset_with_cache(source, path)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=404, detail="Not Found") from exc
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        raise HTTPException(status_code=502, detail="Upstream fetch failed") from exc
    headers = {
        **ASSET_HEADERS,
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
    }
    return Response(content=raw, media_type=media_type, headers=headers)


_FONT_FILE = (
    Path(__file__).resolve().parent.parent
    / "static"
    / "fonts"
    / "PretendardVariable.woff2"
)


@viewer_router.get("/share/{token}/font", response_model=None)
async def view_share_font(token: str, request: Request) -> Response:
    """Serve the bundled body font so shared pages look the same on every PC."""
    opened = await _open_share(token, _locale(request))
    if isinstance(opened, Response):
        return opened
    # The font never changes between releases, so browsers may keep it.
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=31536000, immutable",
    }
    return FileResponse(_FONT_FILE, media_type="font/woff2", headers=headers)
