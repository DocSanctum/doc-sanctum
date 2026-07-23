from __future__ import annotations

import httpx
import pytest
from backend.app.services.gitlab import (
    _content_raw_url,
    _gitlab_headers,
    _parse_gitlab_url,
    _project_api_base,
    fetch_gitlab_tree,
)


def test_parse_gitlab_com_url():
    host, project_path = _parse_gitlab_url("https://gitlab.com/group/project")
    assert (host, project_path) == ("gitlab.com", "group/project")


def test_parse_gitlab_com_url_with_nested_subgroups():
    """Unlike GitHub's fixed owner/repo, GitLab project paths can nest
    arbitrarily deep under groups/subgroups."""
    host, project_path = _parse_gitlab_url("https://gitlab.com/group/subgroup/project")
    assert (host, project_path) == ("gitlab.com", "group/subgroup/project")


def test_parse_gitlab_url_with_git_suffix():
    host, project_path = _parse_gitlab_url("https://gitlab.com/group/project.git")
    assert (host, project_path) == ("gitlab.com", "group/project")


def test_parse_self_hosted_gitlab_url():
    host, project_path = _parse_gitlab_url("https://gitlab.mycompany.com/group/project")
    assert (host, project_path) == ("gitlab.mycompany.com", "group/project")


def test_parse_gitlab_url_missing_project_raises():
    with pytest.raises(ValueError):
        _parse_gitlab_url("https://gitlab.com/group")


def test_project_api_base_url_encodes_nested_path():
    assert (
        _project_api_base("gitlab.com", "group/subgroup/project")
        == "https://gitlab.com/api/v4/projects/group%2Fsubgroup%2Fproject"
    )


def test_project_api_base_uses_self_hosted_host():
    """gitlab.com and self-hosted GitLab both serve the API off <host>/api/v4
    — no api-host split like GitHub's api.github.com vs GHE's /api/v3."""
    assert (
        _project_api_base("gitlab.mycompany.com", "group/project")
        == "https://gitlab.mycompany.com/api/v4/projects/group%2Fproject"
    )


def test_content_raw_url_encodes_file_path():
    assert (
        _content_raw_url("gitlab.com", "group/project", "docs/intro.md")
        == "https://gitlab.com/api/v4/projects/group%2Fproject/repository/files/docs%2Fintro.md/raw"
    )


def test_gitlab_headers_includes_given_private_token():
    headers = _gitlab_headers("glpat-test123")
    assert headers["PRIVATE-TOKEN"] == "glpat-test123"


def test_gitlab_headers_omits_auth_when_no_token():
    headers = _gitlab_headers(None)
    assert "PRIVATE-TOKEN" not in headers


@pytest.mark.asyncio
async def test_fetch_gitlab_tree_reuses_page_one_auth_decision(monkeypatch):
    """Once page 1 establishes that auth is required (private repo), later
    pages must go straight to an authenticated request instead of
    re-attempting anonymous-first on every page — otherwise a large repo's
    100+ pages would each cost two requests instead of one."""
    calls: list[tuple[int, bool]] = []

    pages = {
        1: [{"id": "sha1", "path": "README.md", "type": "blob"}],
        2: [{"id": "sha2", "path": "docs/intro.md", "type": "blob"}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        has_auth = "PRIVATE-TOKEN" in request.headers
        calls.append((page, has_auth))
        if not has_auth:
            return httpx.Response(404, json={"error": "not found"})
        next_page = "2" if page == 1 else ""
        headers = {"x-next-page": next_page} if next_page else {}
        return httpx.Response(200, json=pages[page], headers=headers)

    transport = httpx.MockTransport(handler)
    orig_init = httpx.AsyncClient.__init__

    def patched_init(self, *a, **kw):
        kw["transport"] = transport
        orig_init(self, *a, **kw)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    result = await fetch_gitlab_tree(
        "https://gitlab.com/group/project", "src-1", token="glpat-test123"
    )

    # page 1: anonymous attempt (rejected) + authenticated retry; page 2:
    # goes straight to authenticated, no anonymous probe.
    assert calls == [(1, False), (1, True), (2, True)]
    paths = {c["path"] for c in result["root"]["children"]}
    assert "README.md" in paths


@pytest.mark.asyncio
async def test_fetch_gitlab_tree_includes_pdf_blobs_alongside_markdown(monkeypatch):
    items = [
        {"id": "sha1", "path": "README.md", "type": "blob"},
        {"id": "sha2", "path": "docs/report.pdf", "type": "blob"},
        {"id": "sha3", "path": "assets/logo.png", "type": "blob"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=items, headers={})

    transport = httpx.MockTransport(handler)
    orig_init = httpx.AsyncClient.__init__

    def patched_init(self, *a, **kw):
        kw["transport"] = transport
        orig_init(self, *a, **kw)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    result = await fetch_gitlab_tree("https://gitlab.com/group/project", "src-1")

    paths = {c["path"] for c in result["root"]["children"]}
    assert paths == {"README.md", "docs"}
    docs_children = next(c for c in result["root"]["children"] if c["path"] == "docs")[
        "children"
    ]
    assert {c["path"] for c in docs_children} == {"docs/report.pdf"}
