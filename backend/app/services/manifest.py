from __future__ import annotations

from typing import Any

import httpx


def _build_tree_from_manifest(
    files: list[dict], source_id: str, base_url: str, source_name: str
) -> dict[str, Any]:
    root: dict[str, Any] = {}
    for entry in files:
        path: str = entry.get("path", "")
        parts = path.split("/")
        node = root
        for i, part in enumerate(parts):
            if part not in node:
                is_last = i == len(parts) - 1
                node[part] = {
                    "__is_file": is_last,
                    "__meta": entry if is_last else {},
                    "__children": {},
                }
            node = node[part]["__children"]

    def to_nodes(d: dict, prefix: str) -> list[dict[str, Any]]:
        nodes = []
        for name, info in sorted(
            d.items(), key=lambda x: (not x[1]["__is_file"], x[0].lower())
        ):
            rel = f"{prefix}/{name}".lstrip("/")
            if info["__is_file"]:
                meta = info["__meta"]
                nodes.append(
                    {
                        "path": rel,
                        "name": name,
                        "is_dir": False,
                        "size": meta.get("size"),
                        "modified_at": meta.get("modified"),
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

    return {
        "source_id": source_id,
        "root": {
            "path": "",
            "name": source_name,
            "is_dir": True,
            "children": to_nodes(root, ""),
        },
    }


async def fetch_manifest_tree(
    base_url: str, source_id: str, source_name: str
) -> dict[str, Any]:
    manifest_url = base_url.rstrip("/") + "/index.json"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(manifest_url)
        if resp.status_code == 404:
            raise FileNotFoundError(f"index.json not found at {manifest_url}")
        resp.raise_for_status()
    data = resp.json()
    if data.get("version") != "1":
        raise ValueError("Unsupported manifest version")
    return _build_tree_from_manifest(
        data.get("files", []), source_id, base_url, source_name
    )
