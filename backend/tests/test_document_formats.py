import os

import pytest

from app.services import document_formats as df

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _read_fixture(name: str) -> bytes:
    with open(os.path.join(FIXTURES, name), "rb") as f:
        return f.read()


def test_is_supported_recognizes_md_and_pdf_case_insensitively():
    assert df.is_supported("docs/readme.md")
    assert df.is_supported("docs/report.PDF")
    assert df.is_supported("report.pdf")
    assert not df.is_supported("image.png")
    assert not df.is_supported("no_extension")


def test_extract_text_markdown_decodes_utf8():
    result = df.extract_text("docs/readme.md", "안녕하세요 hello".encode())
    assert result.text == "안녕하세요 hello"
    assert result.pages is None
    assert result.page_starts is None


def test_extract_text_pdf_returns_pages_and_page_starts():
    raw = _read_fixture("sample.pdf")
    result = df.extract_text("docs/sample.pdf", raw)
    assert result.pages is not None
    assert len(result.pages) == 3
    assert "zephyrquartz-page2-marker" in result.text
    marker_offset = result.text.index("zephyrquartz-page2-marker")
    assert df.page_for_offset(result.page_starts, marker_offset) == 2


def test_extract_text_pdf_partial_extraction_skips_blank_page_without_error():
    raw = _read_fixture("mixed.pdf")
    result = df.extract_text("docs/mixed.pdf", raw)
    # Page 2 is blank/image-only; page 1 and page 3 have text and must both
    # still be recovered without the blank page raising anything.
    assert "Page one has text." in result.text
    assert "kestrelbramble-marker" in result.text
    physical_pages_with_text = [p for p, _ in result.page_starts]
    assert physical_pages_with_text == [1, 3]


def test_extract_text_pdf_whole_document_empty_raises():
    raw = _read_fixture("scanned.pdf")
    with pytest.raises(df.NoExtractableTextError):
        df.extract_text("docs/scanned.pdf", raw)


def test_extract_text_pdf_corrupted_bytes_raises():
    with pytest.raises(df.NoExtractableTextError):
        df.extract_text("docs/broken.pdf", b"not a real pdf file at all")
