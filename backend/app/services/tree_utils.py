from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Transient upstream failures worth retrying: server-side 5xx (a large repo's
# paginated tree walk against e.g. GitLab occasionally returns a 502 partway
# through) and network-level timeouts / transport errors. 4xx are deliberately
# excluded — they're either permanent or handled by the auth fallback below.
_RETRY_STATUS_CODES = frozenset({500, 502, 503, 504})
_MAX_ATTEMPTS = 4
_BACKOFF_BASE_SECONDS = 0.5


async def get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    """GET a URL, retrying a bounded number of times on transient failures
    (5xx responses, timeouts, transport errors) with exponential backoff.

    A non-transient response — including any 4xx — is returned on the first
    attempt for the caller to handle. When the retry budget is exhausted the
    last 5xx response is returned as-is (so the caller's raise_for_status still
    raises it), or the last transport error is re-raised. Without this a single
    transient 5xx on one page of a 100+-page tree traversal fails the whole
    fetch and flips the source to "error"."""
    resp: httpx.Response | None = None
    transient_exc: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        transient_exc = None
        resp = None
        try:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code not in _RETRY_STATUS_CODES:
                return resp
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            transient_exc = exc

        if attempt == _MAX_ATTEMPTS - 1:
            break

        delay = _BACKOFF_BASE_SECONDS * (2**attempt) + random.uniform(0, 0.25)
        detail = (
            f"HTTP {resp.status_code}"
            if resp is not None
            else type(transient_exc).__name__
        )
        logger.warning(
            "Transient failure (%s) fetching %s; retrying %d/%d in %.1fs",
            detail,
            url,
            attempt + 1,
            _MAX_ATTEMPTS - 1,
            delay,
        )
        await asyncio.sleep(delay)

    if resp is not None:
        return resp
    assert transient_exc is not None  # loop always sets one of resp/transient_exc
    raise transient_exc


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
    configured. Each attempt is retried on transient failures via get_with_retry.

    Attaching a token unconditionally can make things *worse* than sending
    no token at all: a valid-but-under-scoped PAT turns a working anonymous
    request against a public repo into a hard 403 (GitLab's
    "insufficient_scope" response), where an anonymous request would have
    succeeded outright. Trying anonymous first means a misconfigured or
    narrowly-scoped token only matters for genuinely private resources.
    """
    resp = await get_with_retry(client, url, headers=no_auth_headers, params=params)
    if resp.status_code in (401, 403, 404) and token_configured:
        resp = await get_with_retry(client, url, headers=auth_headers, params=params)
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
