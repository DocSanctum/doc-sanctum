"""Standalone HTML pages for view-only share links.

Teammates open these from other PCs, where the Vue frontend is unreachable,
so Markdown is rendered here into one self-contained page. Raw HTML in the
source is escaped rather than passed through, and the page ships with a CSP
that allows no scripts at all.
"""

from __future__ import annotations

from html import escape

from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable(
    ["table", "strikethrough"]
)

# The token sits in the URL path, so a Referer header would leak it to any
# site a teammate clicks through to from the shared document.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; img-src https: data:; "
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


def render_markdown_page(path: str, markdown: str) -> str:
    name = path.rsplit("/", 1)[-1]
    header = (
        f"<header><span class='name'>{escape(name)}</span>"
        "<span>DocSanctum · read-only</span></header>"
    )
    return _page(name, header + _md.render(markdown))


def render_notice_page(message: str) -> str:
    return _page("DocSanctum", f"<p class='notice'>{escape(message)}</p>")
