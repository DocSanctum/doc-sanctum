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
