from __future__ import annotations

import pytest
from backend.app.services.github import (
    _api_tree_url,
    _build_tree,
    _content_api_url,
    _github_headers,
    _parse_github_url,
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


def test_github_headers_includes_token_from_env(monkeypatch):
    """Verifies the PAT is carried into the Authorization header once it
    reaches the container as an environment variable.

    `token` scheme (not `Bearer`) is used since some older self-hosted GHE
    instances only accept the former.
    """
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
    headers = _github_headers()
    assert headers["Authorization"] == "token ghp_test123"


def test_github_headers_omits_auth_when_no_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    headers = _github_headers()
    assert "Authorization" not in headers


def test_build_tree_carries_blob_sha_on_files_only():
    """Each leaf file node must expose the git blob sha from the tree API so
    sync_source_index can detect unchanged files without downloading them;
    directory nodes have no sha of their own."""
    nodes = _build_tree(
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
