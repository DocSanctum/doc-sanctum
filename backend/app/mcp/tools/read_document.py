import json
import os
from typing import Any

import httpx
from sqlalchemy import text

from ...core.database import async_session_factory
from ...models.source import Source
from ...services.github import _content_api_url, _github_headers, _parse_github_url
from ...services.gitlab import _content_raw_url, _gitlab_headers, _parse_gitlab_url
from ...services.tree_utils import request_with_auth_fallback
from ..cache import get_cached_content, mark_stale_content, set_cached_content


async def _read_local(source: Source, path: str) -> str:
    expanded = os.path.expanduser(source.path)
    safe_root = os.path.realpath(expanded)
    target = os.path.realpath(os.path.join(expanded, path))
    if not target.startswith(safe_root + os.sep) and target != safe_root:
        raise ValueError("Access denied: path traversal detected")
    if not os.path.isfile(target):
        raise ValueError(f"File not found: {path}")
    with open(target, encoding="utf-8") as f:
        return f.read()


async def _read_github(source: Source, path: str) -> str:
    host, owner, repo = _parse_github_url(source.path)
    url = _content_api_url(host, owner, repo, path)
    # Accept: application/vnd.github.v3.raw returns the raw file bytes
    # directly from the Contents API, instead of a JSON envelope with the
    # content base64-encoded.
    raw_accept = {"Accept": "application/vnd.github.v3.raw"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await request_with_auth_fallback(
            client,
            url,
            no_auth_headers=raw_accept,
            auth_headers={**_github_headers(), **raw_accept},
            token_configured=bool(os.getenv("GITHUB_TOKEN")),
        )
    if resp.status_code == 404:
        raise ValueError(f"File not found: {path}")
    resp.raise_for_status()
    return resp.text


async def _read_gitlab(source: Source, path: str) -> str:
    host, project_path = _parse_gitlab_url(source.path)
    url = _content_raw_url(host, project_path, path)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await request_with_auth_fallback(
            client,
            url,
            no_auth_headers={},
            auth_headers=_gitlab_headers(),
            token_configured=bool(os.getenv("GITLAB_TOKEN")),
        )
    if resp.status_code == 404:
        raise ValueError(f"File not found: {path}")
    resp.raise_for_status()
    return resp.text


async def _read_http(source: Source, path: str) -> str:
    base = source.path.rstrip("/")
    url = f"{base}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
    if resp.status_code == 404:
        raise ValueError(f"File not found: {path}")
    resp.raise_for_status()
    return resp.text


async def _fetch_remote(source: Source, path: str) -> str:
    if source.type == "github":
        return await _read_github(source, path)
    if source.type == "gitlab":
        return await _read_gitlab(source, path)
    return await _read_http(source, path)


async def read_with_cache(
    source: Source, path: str
) -> tuple[str, dict[str, Any] | None]:
    """Read document content, applying the (source_id, path) content cache to
    remote sources only (FR-004, FR-005). Returns (content, warning_or_None)."""
    if source.type == "local":
        return await _read_local(source, path), None

    cached = get_cached_content(source.id, path)
    if cached is not None and not cached["stale"]:
        return cached["data"], None

    try:
        content = await _fetch_remote(source, path)
        set_cached_content(source.id, path, content)
        return content, None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (403, 429) and cached is not None:
            mark_stale_content(source.id, path)
            warning = {
                "source_id": source.id,
                "source_name": source.name,
                "reason": "rate_limit",
                "message": "GitHub API rate limit exceeded. Serving cached content.",
                "stale": True,
            }
            return cached["data"], warning
        raise


async def read_document_handler(source_id: str, path: str) -> str:
    """Read the full content of a specific MD file.

    Args:
        source_id: UUID of the source containing the file.
        path: Relative file path from the source root (e.g. guide/intro.md).
    """
    async with async_session_factory() as session:
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
        raise ValueError(f"Source not found: {source_id}")

    source = Source.from_row(dict(row))
    content, warning = await read_with_cache(source, path)

    result: dict[str, Any] = {
        "path": path,
        "source_id": source.id,
        "source_name": source.name,
        "content": content,
    }
    if warning:
        result["warning"] = warning
    return json.dumps(result, ensure_ascii=False)
