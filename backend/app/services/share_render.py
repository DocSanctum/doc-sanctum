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
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

from .document_formats import image_media_type
from .markdown_alerts import alerts_plugin

_md = (
    MarkdownIt("commonmark", {"html": False, "linkify": False})
    .enable(["table", "strikethrough"])
    .use(front_matter_plugin)
    .use(footnote_plugin)
    .use(tasklists_plugin)
    .use(alerts_plugin)
)

# Wrapping tables lets wide ones scroll sideways on phones while the table
# itself still spans the full text width on larger screens.
_md.add_render_rule(
    "table_open",
    lambda self, tokens, idx, options, env: "<div class='table-wrap'><table>",
)
_md.add_render_rule(
    "table_close", lambda self, tokens, idx, options, env: "</table></div>"
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
  --subtle:#f9fafb; --code-bg:#f3f4f6; --link:#2563eb; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#111827; --fg:#e5e7eb; --muted:#9ca3af; --border:#374151;
    --subtle:#1a2232; --code-bg:#1f2937; --link:#60a5fa; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font: 16px/1.75 -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo",
    "Malgun Gothic", "Noto Sans KR", sans-serif;
  letter-spacing:-0.01em; word-break:keep-all; overflow-wrap:break-word;
  -webkit-font-smoothing:antialiased; }
.bar { position:sticky; top:0; z-index:1; background:var(--bg);
  border-bottom:1px solid var(--border); }
.bar-inner { max-width:820px; margin:0 auto; padding:10px 16px; display:flex;
  align-items:center; gap:12px; font-size:13px; line-height:1.4; }
.doc { min-width:0; flex:1; display:flex; flex-direction:column; }
.doc .name { font-weight:600; font-size:14px; overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap; }
.doc .folder { color:var(--muted); overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap; }
.badge { flex:none; color:var(--muted); border:1px solid var(--border);
  border-radius:999px; padding:2px 10px; font-size:12px; white-space:nowrap; }
main { max-width:820px; margin:0 auto; padding:24px 16px 80px; }
main > :first-child { margin-top:0; }
a { color:var(--link); text-underline-offset:2px; }
h1,h2,h3,h4,h5,h6 { line-height:1.35; letter-spacing:-0.02em; margin:2em 0 .6em;
  font-weight:700; }
h1 { font-size:1.875em; margin-top:.4em; }
h2 { font-size:1.45em; padding-bottom:.3em; border-bottom:1px solid var(--border); }
h3 { font-size:1.2em; } h4 { font-size:1.05em; }
hr { border:0; border-top:1px solid var(--border); margin:2.5em 0; }
hr + h1, hr + h2, hr + h3 { margin-top:0; }
hr + h2 { border-bottom:0; padding-bottom:0; }
p, ul, ol, blockquote, pre, .table-wrap { margin:0 0 1.1em; }
li { margin:.25em 0; } li > ul, li > ol { margin:.25em 0 0; }
img { max-width:100%; height:auto; border-radius:6px; }
code { background:var(--code-bg); padding:.15em .4em; border-radius:4px; font-size:.875em;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  letter-spacing:0; word-break:break-word; }
pre { background:var(--code-bg); padding:14px 16px; border-radius:8px; overflow-x:auto;
  line-height:1.55; }
pre code { background:none; padding:0; font-size:.85em; word-break:normal; }
blockquote { padding:0 1em; color:var(--muted); border-left:4px solid var(--border); }
.table-wrap { overflow-x:auto; border:1px solid var(--border); border-radius:8px; }
table { border-collapse:collapse; width:100%; font-size:.94em; line-height:1.6; }
th,td { padding:8px 12px; text-align:left; vertical-align:top; min-width:5.5em;
  border-bottom:1px solid var(--border); }
th + th, td + td { border-left:1px solid var(--border); }
th { background:var(--subtle); font-weight:600; white-space:nowrap; }
tr:last-child td { border-bottom:0; }
td code, th code { white-space:nowrap; }
.notice { text-align:center; color:var(--muted); padding-top:20vh; }
.footnotes-sep { margin-top:2.5em; }
.footnotes { color:var(--muted); font-size:.9em; }
.contains-task-list { list-style:none; padding-left:1.2em; }
.task-list-item-checkbox { margin-right:.5em; }
.markdown-alert { --alert:#2563eb; margin:1.2em 0; padding:.5em 1em; color:var(--fg);
  border-left:4px solid var(--alert); border-radius:0 6px 6px 0;
  background:color-mix(in srgb, var(--alert) 8%, transparent); }
.markdown-alert p { margin:.4em 0; }
.markdown-alert-title { font-weight:600; color:var(--alert); }
summary.markdown-alert-title { cursor:pointer; }
.markdown-alert-tip { --alert:#16a34a; } .markdown-alert-important { --alert:#9333ea; }
.markdown-alert-warning { --alert:#ca8a04; } .markdown-alert-caution { --alert:#dc2626; }
@media print { .bar { position:static; } .table-wrap { overflow:visible; } }
"""


def _page(title: str, body: str, bar: str = "") -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<meta name='robots' content='noindex'>"
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body>{bar}<main>{body}</main></body></html>"
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
    folder, _, name = path.rpartition("/")
    folder_line = f"<span class='folder'>{escape(folder)}</span>" if folder else ""
    bar = (
        "<header class='bar'><div class='bar-inner'><div class='doc'>"
        f"<span class='name' title='{escape(path)}'>{escape(name)}</span>{folder_line}"
        "</div><span class='badge'>Read-only · DocSanctum</span></div></header>"
    )
    tokens = _md.parse(markdown)
    if asset_url is not None:
        for image in _image_tokens(tokens):
            image_path = _local_image_path(path, image)
            if image_path:
                image.attrSet("src", asset_url(image_path))
                image.attrSet("loading", "lazy")
    body = _md.renderer.render(tokens, _md.options, {})
    return _page(name, body, bar)


def render_notice_page(message: str) -> str:
    return _page("DocSanctum", f"<p class='notice'>{escape(message)}</p>")
