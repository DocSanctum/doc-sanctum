from __future__ import annotations

import httpx
import pytest
from backend.app.services.tree_utils import build_blob_tree, request_with_auth_fallback


def test_build_blob_tree_carries_blob_sha_on_files_only():
    """Each leaf file node must expose the git blob sha from the tree API so
    sync_source_index can detect unchanged files without downloading them;
    directory nodes have no sha of their own. Shared by GitHub and GitLab
    tree fetching, since both APIs return a blob sha per file."""
    nodes = build_blob_tree(
        [
            {"path": "docs/intro.md", "sha": "sha-intro"},
            {"path": "README.md", "sha": "sha-readme"},
        ]
    )
    by_name = {n["name"]: n for n in nodes}

    assert by_name["README.md"]["sha"] == "sha-readme"
    assert "sha" not in by_name["docs"]

    intro = by_name["docs"]["children"][0]
    assert intro["path"] == "docs/intro.md"
    assert intro["sha"] == "sha-intro"


@pytest.mark.asyncio
async def test_auth_fallback_uses_anonymous_response_when_it_succeeds():
    """A misconfigured or under-scoped token must not break access that
    would work anonymously (the GitLab insufficient_scope case: a valid PAT
    without the right scope turned a working public-repo request into a
    403). The anonymous attempt should be preferred whenever it succeeds,
    and auth should not even be attempted."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.headers))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await request_with_auth_fallback(
            client,
            "https://example.com/x",
            no_auth_headers={},
            auth_headers={"Authorization": "token secret"},
            token_configured=True,
        )

    assert resp.status_code == 200
    assert len(calls) == 1
    assert "authorization" not in calls[0]


@pytest.mark.asyncio
async def test_auth_fallback_retries_with_token_when_anonymous_is_rejected():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.headers))
        if "Authorization" in request.headers:
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await request_with_auth_fallback(
            client,
            "https://example.com/x",
            no_auth_headers={},
            auth_headers={"Authorization": "token secret"},
            token_configured=True,
        )

    assert resp.status_code == 200
    assert len(calls) == 2
    assert "authorization" not in calls[0]
    assert calls[1]["authorization"] == "token secret"


@pytest.mark.asyncio
async def test_auth_fallback_does_not_retry_without_a_configured_token():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.headers))
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await request_with_auth_fallback(
            client,
            "https://example.com/x",
            no_auth_headers={},
            auth_headers={},
            token_configured=False,
        )

    assert resp.status_code == 404
    assert len(calls) == 1
