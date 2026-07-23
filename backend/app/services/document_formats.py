from __future__ import annotations

import os
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

SUPPORTED_EXTENSIONS = frozenset({".md", ".pdf"})


class NoExtractableTextError(Exception):
    """Raised when a document's extracted text is empty across its entire
    content (e.g. a scanned PDF with no text layer, or a corrupted file) —
    the whole-document failure path, as opposed to a single blank page
    within an otherwise-readable document."""


def is_supported(name_or_path: str) -> bool:
    return os.path.splitext(name_or_path)[1].lower() in SUPPORTED_EXTENSIONS


@dataclass
class ExtractedDocument:
    text: str
    pages: list[str] | None
    # (1-based physical page number, char offset in `text` where that page's
    # content begins) for each page that actually contributed text — a blank
    # page has no entry here, so page_for_offset() must resolve by "last
    # page number whose offset is <= the target", not by list position.
    page_starts: list[tuple[int, int]] | None


def _extract_pdf(raw: bytes) -> ExtractedDocument:
    try:
        reader = PdfReader(BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as exc:
        raise NoExtractableTextError(f"Could not parse PDF: {exc}") from exc

    text_parts: list[str] = []
    page_starts: list[tuple[int, int]] = []
    offset = 0
    for page_number, page_text in enumerate(pages, start=1):
        stripped = page_text.strip()
        if not stripped:
            continue
        if text_parts:
            offset += len("\n\n")
        page_starts.append((page_number, offset))
        text_parts.append(stripped)
        offset += len(stripped)
    text = "\n\n".join(text_parts)

    if not text.strip():
        raise NoExtractableTextError(
            "No extractable text in any page of this PDF (possibly a "
            "scanned/image-only document, or every page is blank)"
        )
    return ExtractedDocument(text=text, pages=pages, page_starts=page_starts)


def extract_text(path: str, raw: bytes) -> ExtractedDocument:
    """Turn a document's raw fetched bytes into indexable text, dispatched by
    the path's extension. Markdown (and anything else not specially
    handled) is decoded as UTF-8 text unchanged; PDF is parsed page-by-page.
    Raises NoExtractableTextError for a PDF with no usable text anywhere in
    it (spec.md FR-007) — callers should let this propagate to their normal
    per-document failure handling, not swallow it silently."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _extract_pdf(raw)
    return ExtractedDocument(text=raw.decode("utf-8"), pages=None, page_starts=None)


def page_for_offset(page_starts: list[tuple[int, int]], char_start: int) -> int:
    """1-based physical page number containing the character offset
    `char_start` in an ExtractedDocument's `text`, given its `page_starts`
    (page_number, char_offset) pairs, in ascending offset order."""
    page_number = page_starts[0][0]
    for number, start in page_starts:
        if start <= char_start:
            page_number = number
        else:
            break
    return page_number
