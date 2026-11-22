"""GitHub "> [!NOTE]" alerts and Obsidian callouts for markdown-it-py.

This mirrors the frontend plugin so shared pages render alerts the same way.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml
from markdown_it.renderer import RendererHTML
from markdown_it.rules_core import StateCore
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict

_KIND_BY_NAME = {
    **dict.fromkeys(
        [
            "note",
            "info",
            "todo",
            "abstract",
            "summary",
            "tldr",
            "example",
            "quote",
            "cite",
        ],
        "note",
    ),
    **dict.fromkeys(["tip", "hint", "success", "check", "done"], "tip"),
    **dict.fromkeys(["important", "question", "help", "faq"], "important"),
    **dict.fromkeys(["warning", "attention"], "warning"),
    **dict.fromkeys(
        ["caution", "danger", "error", "bug", "failure", "fail", "missing"], "caution"
    ),
}

_MARKER = re.compile(r"^\[!([A-Za-z]+)\]([+-]?)[ \t]*(.*)$")


def _find_close(tokens: list[Token], open_idx: int) -> int:
    depth = 0
    for j in range(open_idx, len(tokens)):
        if tokens[j].type == "blockquote_open":
            depth += 1
        elif tokens[j].type == "blockquote_close":
            depth -= 1
            if depth == 0:
                return j
    return -1


def _alerts_rule(state: StateCore) -> None:
    tokens = state.tokens
    i = 0
    while i < len(tokens):
        open_token = tokens[i]
        is_candidate = (
            open_token.type == "blockquote_open"
            and i + 2 < len(tokens)
            and tokens[i + 1].type == "paragraph_open"
            and tokens[i + 2].type == "inline"
        )
        if not is_candidate:
            i += 1
            continue
        inline = tokens[i + 2]
        first_line, *rest = inline.content.split("\n")
        match = _MARKER.match(first_line)
        close_idx = _find_close(tokens, i)
        if not match or close_idx == -1:
            i += 1
            continue

        name, fold, custom_title = (
            match.group(1).lower(),
            match.group(2),
            match.group(3),
        )
        kind = _KIND_BY_NAME.get(name, "note")
        open_token.attrJoin("class", f"markdown-alert markdown-alert-{kind}")
        if fold:
            open_token.tag = "details"
            tokens[close_idx].tag = "details"
            if fold == "+":
                open_token.attrSet("open", "")
        title = Token("alert_title", "summary" if fold else "p", 0)
        title.content = custom_title.strip() or name.capitalize()

        # The marker line becomes the title; drop its paragraph if nothing else was in it.
        if rest:
            inline.content = "\n".join(rest)
            tokens.insert(i + 1, title)
        else:
            tokens[i + 1 : i + 4] = [title]
        i += 1


def _render_alert_title(
    self: RendererHTML,
    tokens: Sequence[Token],
    idx: int,
    options: OptionsDict,
    env: EnvType,
) -> str:
    token = tokens[idx]
    content = escapeHtml(token.content)
    return f'<{token.tag} class="markdown-alert-title">{content}</{token.tag}>'


def alerts_plugin(md: MarkdownIt) -> None:
    md.core.ruler.before("inline", "alerts", _alerts_rule)
    md.add_render_rule("alert_title", _render_alert_title)
