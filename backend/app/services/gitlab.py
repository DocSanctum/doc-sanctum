from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

import httpx

from .tree_utils import build_blob_tree, request_with_auth_fallback


def _gitlab_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    token = os.getenv("GITLAB_TOKEN")
    if token:
        # PRIVATE-TOKEN is GitLab's long-standing scheme, supported
        # identically on gitlab.com and every self-hosted CE/EE version.
        headers["PRIVATE-TOKEN"] = token
    return headers


def _parse_gitlab_url(url: str) -> tuple[str, str]:
    """Extract host and project path from a gitlab.com or self-hosted GitLab
    URL. Unlike GitHub, GitLab project paths can include nested groups
    (group/subgroup/project), so the path segment count is variable."""
    m = re.match(r"https?://([^/]+)/(.+?)/?$", url)
    if not m:
        raise ValueError(f"Invalid GitLab URL: {url}")
    host, project_path = m.group(1), m.group(2)
    if project_path.endswith(".git"):
        project_path = project_path[: -len(".git")]
    if "/" not in project_path:
        raise ValueError(f"Invalid GitLab URL: {url}")
    return host, project_path


def _project_api_base(host: str, project_path: str) -> str:
    """gitlab.com and self-hosted GitLab both serve the REST API off
    <host>/api/v4 — unlike GitHub, there's no separate API host to special-case."""
    encoded = quote(project_path, safe="")
    return f"https://{host}/api/v4/projects/{encoded}"


def _content_raw_url(host: str, project_path: str, path: str) -> str:
    encoded_path = quote(path, safe="")
    return (
        f"{_project_api_base(host, project_path)}/repository/files/{encoded_path}/raw"
    )


async def fetch_gitlab_tree(url: str, source_id: str) -> dict[str, Any]:
    host, project_path = _parse_gitlab_url(url)
    base = _project_api_base(host, project_path)
    token_configured = bool(os.getenv("GITLAB_TOKEN"))
    md_blobs: list[dict[str, Any]] = []
    page = 1
    # Determined from page 1's response, then reused as-is for every later
    # page — re-probing anonymous-then-auth on each of a large repo's 100+
    # pages would double the request count for private repos.
    use_auth = False
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        while True:
            tree_url = f"{base}/repository/tree"
            params: dict[str, str | int] = {
                "recursive": "true",
                "per_page": 100,
                "page": page,
            }
            if page == 1:
                resp = await request_with_auth_fallback(
                    client,
                    tree_url,
                    params=params,
                    no_auth_headers={},
                    auth_headers=_gitlab_headers(),
                    token_configured=token_configured,
                )
                use_auth = "PRIVATE-TOKEN" in resp.request.headers
            else:
                resp = await client.get(
                    tree_url,
                    params=params,
                    headers=_gitlab_headers() if use_auth else {},
                )
            resp.raise_for_status()
            items = resp.json()
            md_blobs.extend(
                {"path": item["path"], "sha": item["id"]}
                for item in items
                if item["type"] == "blob" and item["path"].endswith(".md")
            )
            next_page = resp.headers.get("x-next-page")
            if not next_page:
                break
            page = int(next_page)
    return {
        "source_id": source_id,
        "root": {
            "path": "",
            "name": project_path.rsplit("/", 1)[-1],
            "is_dir": True,
            "children": build_blob_tree(md_blobs),
        },
    }
