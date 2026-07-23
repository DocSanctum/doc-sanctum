from __future__ import annotations

import backend.app.services.tree_utils as tree_utils
import httpx
import pytest
from backend.app.services.tree_utils import (
    build_blob_tree,
    get_with_retry,
    request_with_auth_fallback,
)


@pytest.fixture
def _no_backoff(monkeypatch):
    """Make retry backoff instantaneous so the retry tests don't actually sleep."""
    monkeypatch.setattr(tree_utils, "_BACKOFF_BASE_SECONDS", 0.0)
    monkeypatch.setattr(tree_utils.random, "uniform", lambda a, b: 0.0)


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


def test_build_blob_tree_treats_pdf_and_markdown_blobs_identically():
    """build_blob_tree has no format-specific branching — it just nests
    whatever blob list it's given (014-pdf-parser-support: format filtering
    happens before this function is called, in document_formats.is_supported)."""
    nodes = build_blob_tree(
        [
            {"path": "README.md", "sha": "sha-readme"},
            {"path": "docs/report.pdf", "sha": "sha-report"},
        ]
    )
    by_name = {n["name"]: n for n in nodes}

    assert by_name["README.md"]["sha"] == "sha-readme"
    report = by_name["docs"]["children"][0]
    assert report["path"] == "docs/report.pdf"
    assert report["sha"] == "sha-report"


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


@pytest.mark.asyncio
async def test_get_with_retry_recovers_from_transient_5xx(_no_backoff):
    """A transient 5xx (e.g. a 502 partway through a large repo's paginated
    tree walk) is retried and succeeds, instead of failing the whole fetch."""
    n = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["count"] += 1
        if n["count"] < 3:
            return httpx.Response(502, text="bad gateway")
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await get_with_retry(client, "https://example.com/x", headers={})

    assert resp.status_code == 200
    assert n["count"] == 3  # two 502s retried, third attempt succeeds


@pytest.mark.asyncio
async def test_get_with_retry_returns_last_5xx_when_budget_exhausted(_no_backoff):
    """A persistent 5xx is retried up to the budget, then returned as-is so the
    caller's raise_for_status still surfaces the error."""
    n = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["count"] += 1
        return httpx.Response(503, text="unavailable")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await get_with_retry(client, "https://example.com/x", headers={})

    assert resp.status_code == 503
    assert n["count"] == tree_utils._MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_get_with_retry_does_not_retry_4xx(_no_backoff):
    """4xx is not transient (permanent, or handled by the auth fallback), so it
    returns on the first attempt without burning the retry budget."""
    n = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["count"] += 1
        return httpx.Response(404, text="nope")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await get_with_retry(client, "https://example.com/x", headers={})

    assert resp.status_code == 404
    assert n["count"] == 1


@pytest.mark.asyncio
async def test_get_with_retry_reraises_transport_error_after_budget(_no_backoff):
    """Network-level failures (timeouts/transport errors) are retried, then the
    last one is re-raised when the budget is exhausted."""
    n = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["count"] += 1
        raise httpx.ConnectTimeout("timed out")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.TimeoutException):
            await get_with_retry(client, "https://example.com/x", headers={})

    assert n["count"] == tree_utils._MAX_ATTEMPTS
