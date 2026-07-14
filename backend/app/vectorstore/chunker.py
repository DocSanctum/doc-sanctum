from __future__ import annotations

import re
from dataclasses import dataclass

from . import tokenizer

# Sized to the embedding model's real input capacity (256 tokens), measured
# with the exact tokenizer that will embed the resulting chunks, rather than
# an approximate character count. The 12.5% overlap ratio matches what the
# previous character-based constants used.
MAX_CHUNK_TOKENS = 256
CHUNK_OVERLAP_TOKENS = 32

# Bumped whenever this chunking algorithm materially changes, so
# rebuild_check._check_chunking_version() can detect the change and trigger
# a full reindex of everything that was chunked under the old rule.
CHUNKING_VERSION = 2

_HEADING_RE = re.compile(r"^#{1,4}\s+.*$", re.MULTILINE)

_content_budget: int | None = None


def _content_token_budget() -> int:
    """MAX_CHUNK_TOKENS minus whatever special-token overhead (e.g. [CLS]/
    [SEP]) the tokenizer adds to every standalone encode() call — computed
    from the tokenizer itself rather than hardcoded, so a chunk built from
    this many "content" tokens still measures <= MAX_CHUNK_TOKENS when it is
    later re-encoded on its own at actual embed time."""
    global _content_budget
    if _content_budget is None:
        _content_budget = MAX_CHUNK_TOKENS - tokenizer.count_tokens("")
    return _content_budget


def _token_overlap_suffix(text: str, n_tokens: int) -> str:
    """Suffix of `text` covering its last `n_tokens` real (non-special)
    tokens, for token-based chunk overlap (replaces the old
    `buf[-CHUNK_OVERLAP_CHARS:]` char-slice)."""
    offsets = tokenizer.token_offsets(text)
    content_offsets = offsets[1:-1] if len(offsets) >= 2 else offsets
    if len(content_offsets) <= n_tokens:
        return text
    char_start = content_offsets[-n_tokens][0]
    return text[char_start:]


@dataclass
class Chunk:
    index: int
    text: str
    char_start: int
    char_end: int


def _split_by_headings(text: str) -> list[tuple[int, str]]:
    starts = [m.start() for m in _HEADING_RE.finditer(text)]
    if not starts:
        return [(0, text)]
    sections: list[tuple[int, str]] = []
    if starts[0] > 0:
        sections.append((0, text[: starts[0]]))
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        sections.append((start, text[start:end]))
    return sections


def _split_fixed(start_offset: int, text: str) -> list[tuple[int, str]]:
    """Fixed-window fallback for a single run of text (no paragraph/heading
    breaks) too long to fit in one chunk. Windows start sized in "content"
    tokens (_content_token_budget()), estimated from the source text's own
    token offsets, but re-encoding an extracted slice on its own can
    occasionally produce a few more tokens than that estimate — WordPiece
    tokenizes a word differently depending on what's around it, so a slice
    boundary landing inside a word can shift the count. Each window is
    therefore verified against the real tokenizer and shrunk until it
    actually fits, guaranteeing MAX_CHUNK_TOKENS rather than approximating
    it."""
    all_offsets = tokenizer.token_offsets(text)
    content_offsets = all_offsets[1:-1] if len(all_offsets) >= 2 else all_offsets
    if not content_offsets:
        return [(start_offset, text)]

    budget = _content_token_budget()
    parts: list[tuple[int, str]] = []
    pos = 0
    n = len(content_offsets)
    while pos < n:
        end = min(pos + budget, n)
        while end > pos + 1:
            char_start = content_offsets[pos][0]
            char_end = content_offsets[end - 1][1]
            if tokenizer.count_tokens(text[char_start:char_end]) <= MAX_CHUNK_TOKENS:
                break
            end -= 1
        char_start = content_offsets[pos][0]
        char_end = content_offsets[end - 1][1]
        parts.append((start_offset + char_start, text[char_start:char_end]))
        if end == n:
            break
        pos += max(end - pos - CHUNK_OVERLAP_TOKENS, 1)
    return parts


def _split_long_section(start_offset: int, section: str) -> list[tuple[int, str]]:
    if tokenizer.count_tokens(section) <= MAX_CHUNK_TOKENS:
        return [(start_offset, section)]

    parts: list[tuple[int, str]] = []
    buf = ""
    buf_start = start_offset
    offset = start_offset
    for para in section.split("\n\n"):
        if not para.strip():
            offset += len(para) + 2
            continue
        if tokenizer.count_tokens(para) > MAX_CHUNK_TOKENS:
            if buf:
                parts.append((buf_start, buf))
                buf = ""
            parts.extend(_split_fixed(offset, para))
            offset += len(para) + 2
            buf_start = offset
            continue
        candidate = f"{buf}\n\n{para}" if buf else para
        if tokenizer.count_tokens(candidate) > MAX_CHUNK_TOKENS and buf:
            parts.append((buf_start, buf))
            overlap_text = _token_overlap_suffix(buf, CHUNK_OVERLAP_TOKENS)
            buf = f"{overlap_text}\n\n{para}"
            buf_start = offset - len(overlap_text)
        else:
            buf = candidate
        offset += len(para) + 2
    if buf.strip():
        parts.append((buf_start, buf))
    return parts


def chunk_markdown(text: str) -> list[Chunk]:
    """Split MD text into chunks along heading boundaries, falling back to
    paragraph-based splitting for long sections. Chunk boundaries overlap
    slightly to reduce context loss."""
    if not text.strip():
        return []

    chunks: list[Chunk] = []
    index = 0
    for start_offset, section in _split_by_headings(text):
        if not section.strip():
            continue
        for part_start, part_text in _split_long_section(start_offset, section):
            stripped = part_text.strip()
            if not stripped:
                continue
            chunks.append(
                Chunk(
                    index=index,
                    text=stripped,
                    char_start=part_start,
                    char_end=part_start + len(part_text),
                )
            )
            index += 1
    return chunks
