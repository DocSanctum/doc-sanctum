from __future__ import annotations

from typing import Any

import httpx


async def request_with_auth_fallback(
    client: httpx.AsyncClient,
    url: str,
    *,
    no_auth_headers: dict[str, str],
    auth_headers: dict[str, str],
    token_configured: bool,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    """Try the request without credentials first, then fall back to the
    authenticated headers only if that's rejected and a token is actually
    configured.

    Attaching a token unconditionally can make things *worse* than sending
    no token at all: a valid-but-under-scoped PAT turns a working anonymous
    request against a public repo into a hard 403 (GitLab's
    "insufficient_scope" response), where an anonymous request would have
    succeeded outright. Trying anonymous first means a misconfigured or
    narrowly-scoped token only matters for genuinely private resources.
    """
    resp = await client.get(url, params=params, headers=no_auth_headers)
    if resp.status_code in (401, 403, 404) and token_configured:
        resp = await client.get(url, params=params, headers=auth_headers)
    return resp


def build_blob_tree(blobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn a flat list of {"path", "sha"} blobs (as returned by GitHub's and
    GitLab's tree APIs) into the nested tree structure the frontend expects.

    Each leaf node carries the git blob sha, which lets sync_source_index
    skip re-downloading unchanged files (see vectorstore/indexer.py)."""
    root: dict[str, Any] = {}
    for blob in blobs:
        parts = blob["path"].split("/")
        node = root
        for i, part in enumerate(parts):
            if part not in node:
                is_last = i == len(parts) - 1
                node[part] = {
                    "__is_file": is_last,
                    "__children": {},
                    "__sha": blob["sha"] if is_last else None,
                }
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
                        "sha": info["__sha"],
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
