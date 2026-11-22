from __future__ import annotations

import pytest
from backend.app.services.share_render import referenced_images, resolve_doc_path


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
