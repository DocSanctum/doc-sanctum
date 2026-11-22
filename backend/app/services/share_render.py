"""Standalone HTML pages for view-only share links.

Teammates open these from other PCs, where the Vue frontend is unreachable,
so Markdown is rendered here into one self-contained page. Raw HTML in the
source is escaped rather than passed through, and the page ships with a CSP
that allows no scripts at all.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from html import escape
from urllib.parse import unquote

from markdown_it import MarkdownIt
from markdown_it.token import Token

from .document_formats import image_media_type

_md = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable(
    ["table", "strikethrough"]
)

# The token sits in the URL path, so a Referer header would leak it to any
# site a teammate clicks through to from the shared document.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' https: data:; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
}

_STYLE = """
:root { --bg:#ffffff; --fg:#1f2937; --muted:#6b7280; --border:#e5e7eb;
  --code-bg:#f3f4f6; --link:#2563eb; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#111827; --fg:#e5e7eb; --muted:#9ca3af; --border:#374151;
    --code-bg:#1f2937; --link:#60a5fa; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font: 16px/1.7 -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo",
    "Malgun Gothic", sans-serif; }
main { max-width: 820px; margin: 0 auto; padding: 32px 16px 64px; }
header { color:var(--muted); font-size:13px; border-bottom:1px solid var(--border);
  padding-bottom:12px; margin-bottom:24px; display:flex; gap:8px; flex-wrap:wrap;
  justify-content:space-between; }
header .name { color:var(--fg); font-weight:600; word-break:break-all; }
a { color:var(--link); }
h1,h2,h3,h4 { line-height:1.3; margin:1.6em 0 .6em; }
h1 { font-size:1.9em; } h2 { font-size:1.45em; border-bottom:1px solid var(--border);
  padding-bottom:.25em; }
img { max-width:100%; }
code { background:var(--code-bg); padding:.15em .35em; border-radius:4px; font-size:.9em;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
pre { background:var(--code-bg); padding:14px 16px; border-radius:8px; overflow-x:auto; }
pre code { background:none; padding:0; }
blockquote { margin:1em 0; padding:0 1em; color:var(--muted);
  border-left:4px solid var(--border); }
table { border-collapse:collapse; display:block; overflow-x:auto; }
th,td { border:1px solid var(--border); padding:6px 12px; }
hr { border:0; border-top:1px solid var(--border); margin:2em 0; }
.notice { text-align:center; color:var(--muted); padding-top:20vh; }
"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<meta name='robots' content='noindex'>"
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body><main>{body}</main></body></html>"
    )


_EXTERNAL_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def resolve_doc_path(current_file: str, ref: str) -> str | None:
    """Resolve a reference written in a document to a source-relative path.
    Returns None for external, empty, or root-escaping references."""
    part = re.split(r"[?#]", ref, maxsplit=1)[0]
    if not part or _EXTERNAL_SCHEME.match(ref) or ref.startswith("//"):
        return None
    segments = [] if part.startswith("/") else current_file.split("/")[:-1]
    for raw in part.split("/"):
        seg = unquote(raw)
        if "/" in seg or "\\" in seg:
            return None
        if seg in ("", "."):
            continue
        if seg == "..":
            if not segments:
                return None
            segments.pop()
            continue
        segments.append(seg)
    return "/".join(segments) or None


def _image_tokens(tokens: list[Token]) -> Iterator[Token]:
    for token in tokens:
        for child in token.children or []:
            if child.type == "image":
                yield child


def _local_image_path(doc_path: str, image: Token) -> str | None:
    src = str(image.attrGet("src") or "")
    path = resolve_doc_path(doc_path, src)
    return path if path and image_media_type(path) else None


def referenced_images(doc_path: str, markdown: str) -> set[str]:
    """Return the source-relative image paths that the document embeds."""
    found = set()
    for image in _image_tokens(_md.parse(markdown)):
        path = _local_image_path(doc_path, image)
        if path:
            found.add(path)
    return found


def render_markdown_page(
    path: str, markdown: str, asset_url: Callable[[str], str] | None = None
) -> str:
    """Render a shared document; asset_url maps each embedded local image
    path to the URL the page should load it from."""
    name = path.rsplit("/", 1)[-1]
    header = (
        f"<header><span class='name'>{escape(name)}</span>"
        "<span>DocSanctum · read-only</span></header>"
    )
    tokens = _md.parse(markdown)
    if asset_url is not None:
        for image in _image_tokens(tokens):
            image_path = _local_image_path(path, image)
            if image_path:
                image.attrSet("src", asset_url(image_path))
                image.attrSet("loading", "lazy")
    body = _md.renderer.render(tokens, _md.options, {})
    return _page(name, header + body)


def render_notice_page(message: str) -> str:
    return _page("DocSanctum", f"<p class='notice'>{escape(message)}</p>")
