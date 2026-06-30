from __future__ import annotations
import os
from typing import Any

from ..models.source import Source
from .github import fetch_github_tree
from .manifest import fetch_manifest_tree


def _build_node(abs_path: str, rel_path: str, name: str) -> dict[str, Any]:
    node: dict[str, Any] = {"path": rel_path, "name": name, "is_dir": False}
    try:
        stat = os.stat(abs_path)
        node["size"] = stat.st_size
        node["modified_at"] = None
    except OSError:
        node["size"] = None
        node["modified_at"] = None
    return node


def _scan_dir(abs_dir: str, rel_dir: str) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []
    try:
        entries = sorted(os.scandir(abs_dir), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        return children

    for entry in entries:
        rel = os.path.join(rel_dir, entry.name).lstrip("/")
        if entry.is_dir(follow_symlinks=False):
            sub = _scan_dir(entry.path, rel)
            if sub:
                children.append({"path": rel, "name": entry.name, "is_dir": True, "children": sub})
        elif entry.name.endswith(".md"):
            children.append(_build_node(entry.path, rel, entry.name))
    return children


async def build_remote_tree(source: Source) -> dict[str, Any]:
    if source.type == "github":
        return await fetch_github_tree(source.path, source.id)
    return await fetch_manifest_tree(source.path, source.id, source.name)


def build_local_tree(source: Source) -> dict[str, Any]:
    root_children = _scan_dir(source.path, "")
    return {
        "source_id": source.id,
        "root": {
            "path": "",
            "name": source.name,
            "is_dir": True,
            "children": root_children,
        },
    }
