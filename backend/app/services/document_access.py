from __future__ import annotations

import os
from typing import Any

import httpx

from ..models.source import Source
from .document_cache import (
    get_cached,
    get_cached_content,
    get_tree_lock,
    mark_stale,
    mark_stale_content,
    set_cached,
    set_cached_content,
)
from .github import _content_api_url, _github_headers, _parse_github_url
from .gitlab import _content_raw_url, _gitlab_headers, _parse_gitlab_url
from .token_resolver import resolve_access_token
from .tree_builder import build_local_tree, build_remote_tree
from .tree_utils import request_with_auth_fallback


def flatten_tree(
    node: dict[str, Any], results: list[dict[str, Any]], source: Source
) -> None:
    if not node.get("is_dir"):
        results.append(
            {
                "path": node["path"],
                "name": node["name"],
                "source_id": source.id,
                "source_name": source.name,
                "source_type": source.type,
                "sha": node.get("sha"),
            }
        )
        return
    for child in node.get("children", []):
        flatten_tree(child, results, source)


async def get_tree_with_cache(
    source: Source,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Returns (tree, warning_or_None)."""
    if source.type == "local":
        return build_local_tree(source), None

    cached = get_cached(source.id)
    if cached is not None and not cached["stale"]:
        return cached["data"], None

    async with get_tree_lock(source.id):
        # Re-check: another coroutine may have populated the cache while we
        # were waiting for the lock (e.g. the initial indexing task and a
        # frontend tree-view request racing right after registration).
        cached = get_cached(source.id)
        if cached is not None and not cached["stale"]:
            return cached["data"], None

        try:
            tree = await build_remote_tree(source)
            set_cached(source.id, tree)
            return tree, None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 429):
                mark_stale(source.id)
                stale = get_cached(source.id)
                warning = {
                    "source_id": source.id,
                    "source_name": source.name,
                    "reason": "rate_limit",
                    "message": "GitHub API rate limit exceeded. Serving cached data.",
                    "stale": True,
                }
                if stale:
                    return stale["data"], warning
            warning = {
                "source_id": source.id,
                "source_name": source.name,
                "reason": "access_error",
                "message": str(exc),
                "stale": False,
            }
            return {
                "source_id": source.id,
                "root": {"is_dir": True, "children": []},
            }, warning
        except Exception as exc:
            warning = {
                "source_id": source.id,
                "source_name": source.name,
                "reason": "access_error",
                "message": str(exc),
                "stale": False,
            }
            return {
                "source_id": source.id,
                "root": {"is_dir": True, "children": []},
            }, warning


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
    token = resolve_access_token(source)
    # Accept: application/vnd.github.v3.raw returns the raw file bytes
    # directly from the Contents API, instead of a JSON envelope with the
    # content base64-encoded.
    raw_accept = {"Accept": "application/vnd.github.v3.raw"}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await request_with_auth_fallback(
            client,
            url,
            no_auth_headers=raw_accept,
            auth_headers={**_github_headers(token), **raw_accept},
            token_configured=bool(token),
        )
    if resp.status_code == 404:
        raise ValueError(f"File not found: {path}")
    resp.raise_for_status()
    return resp.text


async def _read_gitlab(source: Source, path: str) -> str:
    host, project_path = _parse_gitlab_url(source.path)
    url = _content_raw_url(host, project_path, path)
    token = resolve_access_token(source)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await request_with_auth_fallback(
            client,
            url,
            no_auth_headers={},
            auth_headers=_gitlab_headers(token),
            token_configured=bool(token),
        )
    if resp.status_code == 404:
        raise ValueError(f"File not found: {path}")
    resp.raise_for_status()
    return resp.text


async def _read_http(source: Source, path: str) -> str:
    base = source.path.rstrip("/")
    url = f"{base}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
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
