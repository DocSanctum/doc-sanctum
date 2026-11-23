from __future__ import annotations

import pytest
from backend.app.services.share_render import (
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
