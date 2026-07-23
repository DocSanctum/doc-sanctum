from __future__ import annotations

import httpx
import pytest
from backend.app.services.github import (
    _api_tree_url,
    _content_api_url,
    _github_headers,
    _parse_github_url,
    fetch_github_tree,
)


def test_parse_github_com_url():
    host, owner, repo = _parse_github_url("https://github.com/owner/repo")
    assert (host, owner, repo) == ("github.com", "owner", "repo")


def test_parse_github_com_url_with_git_suffix():
    host, owner, repo = _parse_github_url("https://github.com/owner/repo.git")
    assert (host, owner, repo) == ("github.com", "owner", "repo")


def test_parse_github_enterprise_url():
    """Reproduces and verifies the fix for a bug where parsing failed because
    GHE uses a corporate domain instead of github.com."""
    host, owner, repo = _parse_github_url("https://github.mycompany.com/owner/repo")
    assert (host, owner, repo) == ("github.mycompany.com", "owner", "repo")


def test_parse_invalid_url_raises():
    with pytest.raises(ValueError):
        _parse_github_url("https://github.com/owner")


def test_api_tree_url_uses_public_api_host():
    assert (
        _api_tree_url("github.com", "owner", "repo")
        == "https://api.github.com/repos/owner/repo/git/trees/HEAD?recursive=1"
    )


def test_api_tree_url_uses_enterprise_api_v3_prefix():
    assert (
        _api_tree_url("github.mycompany.com", "owner", "repo")
        == "https://github.mycompany.com/api/v3/repos/owner/repo/git/trees/HEAD?recursive=1"
    )


def test_content_api_url_uses_public_api_host():
    assert (
        _content_api_url("github.com", "owner", "repo", "docs/intro.md")
        == "https://api.github.com/repos/owner/repo/contents/docs/intro.md"
    )


def test_content_api_url_uses_enterprise_api_v3_prefix():
    """raw.<host> vs <host>/raw depends on GHE subdomain isolation, so file
    content is fetched through the same versioned API host as the tree
    instead of guessing a raw-content URL shape."""
    assert (
        _content_api_url("github.mycompany.com", "owner", "repo", "docs/intro.md")
        == "https://github.mycompany.com/api/v3/repos/owner/repo/contents/docs/intro.md"
    )


def test_github_headers_includes_given_token():
    """Verifies the PAT is carried into the Authorization header. Callers
    resolve the token themselves (per-source or global env — see
    services/token_resolver.py) and pass it in explicitly.

    `token` scheme (not `Bearer`) is used since some older self-hosted GHE
    instances only accept the former.
    """
    headers = _github_headers("ghp_test123")
    assert headers["Authorization"] == "token ghp_test123"


def test_github_headers_omits_auth_when_no_token():
    headers = _github_headers(None)
    assert "Authorization" not in headers


@pytest.mark.asyncio
async def test_fetch_github_tree_includes_pdf_blobs_alongside_markdown(monkeypatch):
    tree_response = {
        "tree": [
            {"path": "README.md", "sha": "sha1", "type": "blob"},
            {"path": "docs/report.pdf", "sha": "sha2", "type": "blob"},
            {"path": "assets/logo.png", "sha": "sha3", "type": "blob"},
            {"path": "docs", "sha": "sha4", "type": "tree"},
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=tree_response)

    transport = httpx.MockTransport(handler)
    orig_init = httpx.AsyncClient.__init__

    def patched_init(self, *a, **kw):
        kw["transport"] = transport
        orig_init(self, *a, **kw)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    result = await fetch_github_tree("https://github.com/owner/repo", "src-1")

    paths = {c["path"] for c in result["root"]["children"]}
    assert paths == {"README.md", "docs"}
    docs_children = next(c for c in result["root"]["children"] if c["path"] == "docs")[
        "children"
    ]
    assert {c["path"] for c in docs_children} == {"docs/report.pdf"}
