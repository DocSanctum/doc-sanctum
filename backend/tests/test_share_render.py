from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from backend.app.services.share_render import (
    has_mermaid,
    page_headers,
    referenced_images,
    render_markdown_page,
    resolve_doc_path,
)


@pytest.mark.parametrize(
    ("current", "ref", "expected"),
    [
        ("guide/intro.md", "images/a.png", "guide/images/a.png"),
        ("guide/intro.md", "./a.png?raw=1#x", "guide/a.png"),
        ("a/b/c.md", "../img/x.png", "a/img/x.png"),
        ("a/b/c.md", "/assets/x.png", "assets/x.png"),
        ("doc.md", "my%20image.png", "my image.png"),
        ("doc.md", "../escape.png", None),
        ("a/b.md", "..%2F..%2Fsecret.png", None),
        ("doc.md", "https://example.com/a.png", None),
        ("doc.md", "//cdn.example.com/a.png", None),
        ("doc.md", "data:image/png;base64,AAAA", None),
    ],
)
def test_resolve_doc_path(current, ref, expected):
    assert resolve_doc_path(current, ref) == expected


def test_referenced_images_lists_only_local_image_files():
    markdown = (
        "![a](img/a.png) ![b](https://x.com/b.png) [link](other.md)\n\n"
        "| t |\n|---|\n| ![c](../c.svg) |\n\n![d](notes.txt)\n"
    )
    assert referenced_images("team/plan.md", markdown) == {"team/img/a.png", "c.svg"}


def test_shared_page_hides_front_matter_and_renders_footnotes_and_tasks():
    page = render_markdown_page(
        "plan.md",
        "---\ntitle: Secret plan\n---\n# Plan\n\nSee note[^1].\n\n- [x] done\n\n[^1]: Detail.\n",
    )
    assert "Secret plan" not in page
    assert 'class="footnote-ref"' in page
    assert "Detail." in page
    assert 'type="checkbox"' in page


def test_shared_page_renders_alerts_and_foldable_callouts():
    page = render_markdown_page(
        "a.md", "> [!WARNING]\n> Back up first.\n\n> [!info]- More <b>\n> hidden\n"
    )
    assert '<blockquote class="markdown-alert markdown-alert-warning">' in page
    assert '<p class="markdown-alert-title">Warning</p>' in page
    assert "[!WARNING]" not in page
    assert '<details class="markdown-alert markdown-alert-note">' in page
    # Titles are escaped like the rest of the document.
    assert '<summary class="markdown-alert-title">More &lt;b&gt;</summary>' in page


def test_shared_page_still_escapes_raw_html():
    page = render_markdown_page("a.md", "<details><summary>x</summary></details>")
    assert "<details>" not in page
    assert "&lt;details&gt;" in page


LONG_DOC = (
    "# Title\n\n## 현재 문제\n\ntext\n\n### Detail `code`\n\n"
    "## Setup\n\n## Setup\n\n[jump](#현재-문제)\n"
)


def test_fenced_code_with_a_known_language_is_highlighted():
    page = render_markdown_page("a.md", "```python\ndef f():\n    return 1\n```\n")
    assert '<code class="language-python">' in page
    assert '<span class="k">def</span>' in page
    assert "pre code .k" in page


def test_unknown_language_falls_back_to_escaped_code():
    page = render_markdown_page("a.md", "```nope\n<b>x</b>\n```\n")
    assert "&lt;b&gt;x&lt;/b&gt;" in page
    assert "<b>x</b>" not in page


def test_headings_get_unique_ids_matching_the_app_viewer():
    page = render_markdown_page("a.md", LONG_DOC)
    assert '<h2 id="현재-문제">' in page
    assert '<h3 id="detail-code">' in page
    assert '<h2 id="setup">' in page
    assert '<h2 id="setup-1">' in page
    assert "href='#현재-문제' aria-hidden='true'>#</a></h2>" in page


def test_long_document_gets_a_table_of_contents_without_the_title():
    page = render_markdown_page("a.md", LONG_DOC)
    assert "<nav class='toc toc-side'" in page
    assert "<details class='toc toc-inline'>" in page
    assert "<li class='toc-l2'><a href='#현재-문제'>현재 문제</a></li>" in page
    assert "<li class='toc-l3'><a href='#detail-code'>Detail code</a></li>" in page
    assert "href='#title'>Title</a>" not in page
    assert page.index("<details class='toc toc-inline'>") > page.index("</h1>")


def test_short_document_has_no_table_of_contents():
    page = render_markdown_page("a.md", "# Title\n\n## One\n\n## Two\n")
    assert "class='toc" not in page


def test_links_to_other_source_files_become_plain_text():
    page = render_markdown_page(
        "guide/intro.md",
        "[design](./design.md), [**root**](/notes/a.md), "
        "[site](https://example.com), [section](#setup)\n",
    )
    assert 'href="./design.md"' not in page
    assert 'href="/notes/a.md"' not in page
    assert (
        '<span class="unshared-link" title="This document is not shared. '
        'Open it in DocSanctum.">design</span>'
    ) in page
    assert (
        '<span class="unshared-link"' in page and "<strong>root</strong></span>" in page
    )
    assert '<a href="https://example.com">site</a>' in page
    assert '<a href="#setup">section</a>' in page


MERMAID_DOC = '# T\n\n```mermaid\nflowchart LR\n  A["<b>x</b>"] --> B\n```\n'


def test_mermaid_blocks_are_left_for_the_diagram_script():
    page = render_markdown_page("a.md", MERMAID_DOC, script_url="tok/mermaid.js")
    assert "<pre class='mermaid'>flowchart LR" in page
    # The source is escaped so only mermaid, in strict mode, interprets it.
    assert "&lt;b&gt;x&lt;/b&gt;" in page
    assert "<script src='tok/mermaid.js'></script></body>" in page


def test_pages_without_a_script_url_have_no_script_tag():
    assert "<script" not in render_markdown_page("a.md", MERMAID_DOC)


def test_has_mermaid_only_matches_mermaid_fences():
    assert has_mermaid(MERMAID_DOC)
    assert not has_mermaid("```python\nprint(1)\n```\n\nmermaid in prose\n")


def test_scripts_are_allowed_only_from_this_server_and_only_when_needed():
    assert "script-src" not in page_headers(False)["Content-Security-Policy"]
    csp = page_headers(True)["Content-Security-Policy"]
    assert csp.endswith("script-src 'self'")
    assert "default-src 'none'" in csp


def test_mermaid_version_matches_the_frontend():
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "backend" / "Dockerfile").read_text()
    pinned = re.search(r"ARG MERMAID_VERSION=(\S+)", dockerfile)
    lock = json.loads((root / "frontend" / "package-lock.json").read_text())
    assert pinned is not None
    assert pinned.group(1) == lock["packages"]["node_modules/mermaid"]["version"]
