from __future__ import annotations

import pytest
from backend.app.services.github import (
    _api_tree_url,
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
    """GHE는 github.com이 아닌 사내 도메인을 쓰므로 파싱이 실패하던 버그 재현 및 수정 확인."""
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
    """PAT가 컨테이너 환경변수로 전달되면 Authorization 헤더에 실리는지 확인."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
    headers = _github_headers()
    assert headers["Authorization"] == "Bearer ghp_test123"


def test_github_headers_omits_auth_when_no_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    headers = _github_headers()
    assert "Authorization" not in headers
