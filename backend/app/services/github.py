from __future__ import annotations

import re
from typing import Any

import httpx

from .tree_utils import build_blob_tree, request_with_auth_fallback

_NO_AUTH_HEADERS = {"Accept": "application/vnd.github+json"}


def _github_headers(token: str | None) -> dict[str, str]:
    headers = dict(_NO_AUTH_HEADERS)
    if token:
        # `token` (not `Bearer`) is the scheme supported since the original
        # v3 API and still accepted on github.com today; some older
        # self-hosted GHE instances don't accept `Bearer`.
        headers["Authorization"] = f"token {token}"
    return headers


def _parse_github_url(url: str) -> tuple[str, str, str]:
    """Extract host, owner, and repo from a github.com or GitHub Enterprise URL."""
    m = re.match(r"https?://([^/]+)/([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if not m:
        raise ValueError(f"Invalid GitHub URL: {url}")
    return m.group(1), m.group(2), m.group(3)


def _api_base_url(host: str) -> str:
    """github.com serves the REST API off api.github.com; GHE serves it off
    the same host under /api/v3 — unlike raw-content URLs, this doesn't
    depend on whether the GHE instance has subdomain isolation enabled."""
    if host == "github.com":
        return "https://api.github.com"
    return f"https://{host}/api/v3"


def _api_tree_url(host: str, owner: str, repo: str) -> str:
    return f"{_api_base_url(host)}/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"


def _content_api_url(host: str, owner: str, repo: str, path: str) -> str:
    return f"{_api_base_url(host)}/repos/{owner}/{repo}/contents/{path}"


async def fetch_github_tree(
    url: str, source_id: str, token: str | None = None
) -> dict[str, Any]:
    host, owner, repo = _parse_github_url(url)
    api_url = _api_tree_url(host, owner, repo)
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await request_with_auth_fallback(
            client,
            api_url,
            no_auth_headers=_NO_AUTH_HEADERS,
            auth_headers=_github_headers(token),
            token_configured=bool(token),
        )
        resp.raise_for_status()
    data = resp.json()
    md_blobs = [
        {"path": item["path"], "sha": item["sha"]}
        for item in data.get("tree", [])
        if item["path"].endswith(".md") and item["type"] == "blob"
    ]
    return {
        "source_id": source_id,
        "root": {
            "path": "",
            "name": f"{owner}/{repo}",
            "is_dir": True,
            "children": build_blob_tree(md_blobs),
        },
    }
