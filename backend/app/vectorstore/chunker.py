from __future__ import annotations

import re
from dataclasses import dataclass

MAX_CHUNK_CHARS = 800
CHUNK_OVERLAP_CHARS = 100

_HEADING_RE = re.compile(r"^#{1,4}\s+.*$", re.MULTILINE)


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
    """Fixed-window fallback for a single paragraph longer than MAX_CHUNK_CHARS."""
    parts: list[tuple[int, str]] = []
    step = MAX_CHUNK_CHARS - CHUNK_OVERLAP_CHARS
    pos = 0
    while pos < len(text):
        end = min(pos + MAX_CHUNK_CHARS, len(text))
        parts.append((start_offset + pos, text[pos:end]))
        if end == len(text):
            break
        pos += step
    return parts


def _split_long_section(start_offset: int, section: str) -> list[tuple[int, str]]:
    if len(section) <= MAX_CHUNK_CHARS:
        return [(start_offset, section)]

    parts: list[tuple[int, str]] = []
    buf = ""
    buf_start = start_offset
    offset = start_offset
    for para in section.split("\n\n"):
        if not para.strip():
            offset += len(para) + 2
            continue
        if len(para) > MAX_CHUNK_CHARS:
            if buf:
                parts.append((buf_start, buf))
                buf = ""
            parts.extend(_split_fixed(offset, para))
            offset += len(para) + 2
            buf_start = offset
            continue
        candidate = f"{buf}\n\n{para}" if buf else para
        if len(candidate) > MAX_CHUNK_CHARS and buf:
            parts.append((buf_start, buf))
            overlap_text = (
                buf[-CHUNK_OVERLAP_CHARS:] if len(buf) > CHUNK_OVERLAP_CHARS else buf
            )
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
    slightly to reduce context loss (research.md §3)."""
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
