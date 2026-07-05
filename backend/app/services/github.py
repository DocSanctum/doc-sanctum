from __future__ import annotations

import os
import re
from typing import Any

import httpx


def _github_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
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


def _build_tree(flat_files: list[str]) -> list[dict[str, Any]]:
    root: dict[str, Any] = {}
    for path in flat_files:
        parts = path.split("/")
        node = root
        for i, part in enumerate(parts):
            if part not in node:
                is_last = i == len(parts) - 1
                node[part] = {"__is_file": is_last, "__children": {}}
            node = node[part]["__children"]

    def to_nodes(d: dict, prefix: str) -> list[dict[str, Any]]:
        nodes = []
        for name, info in sorted(
            d.items(), key=lambda x: (not x[1]["__is_file"], x[0].lower())
        ):
            rel = f"{prefix}/{name}".lstrip("/")
            if info["__is_file"]:
                nodes.append(
                    {
                        "path": rel,
                        "name": name,
                        "is_dir": False,
                        "size": None,
                        "modified_at": None,
                    }
                )
            else:
                children = to_nodes(info["__children"], rel)
                if children:
                    nodes.append(
                        {
                            "path": rel,
                            "name": name,
                            "is_dir": True,
                            "children": children,
                        }
                    )
        return nodes

    return to_nodes(root, "")


async def fetch_github_tree(url: str, source_id: str) -> dict[str, Any]:
    host, owner, repo = _parse_github_url(url)
    api_url = _api_tree_url(host, owner, repo)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(api_url, headers=_github_headers())
        resp.raise_for_status()
    data = resp.json()
    md_paths = [
        item["path"]
        for item in data.get("tree", [])
        if item["path"].endswith(".md") and item["type"] == "blob"
    ]
    return {
        "source_id": source_id,
        "root": {
            "path": "",
            "name": f"{owner}/{repo}",
            "is_dir": True,
            "children": _build_tree(md_paths),
        },
    }
