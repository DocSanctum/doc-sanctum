from __future__ import annotations

import re
from typing import Any

import httpx


def _parse_github_url(url: str) -> tuple[str, str]:
    """Extract owner and repo from a GitHub URL."""
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if not m:
        raise ValueError(f"Invalid GitHub URL: {url}")
    return m.group(1), m.group(2)


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
    owner, repo = _parse_github_url(url)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            api_url, headers={"Accept": "application/vnd.github+json"}
        )
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
