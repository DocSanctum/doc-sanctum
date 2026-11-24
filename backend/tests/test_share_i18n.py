from __future__ import annotations

import pytest
from backend.app.services.share_i18n import MESSAGES, pick_locale
from backend.app.services.share_render import render_markdown_page, render_notice_page


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "en"),
        ("", "en"),
        ("ko-KR,ko;q=0.9,en-US;q=0.8", "ko"),
        ("en-US,en;q=0.9,ko;q=0.8", "en"),
        ("fr-FR,fr;q=0.9,ko;q=0.5", "ko"),
        ("de,fr", "en"),
        ("en;q=0.3, ko;q=0.7", "ko"),
        ("ko;q=0, en", "en"),
        ("KO", "ko"),
        ("ko;q=abc, en;q=0.1", "en"),
    ],
)
def test_pick_locale_follows_browser_preferences(header, expected):
    assert pick_locale(header) == expected


def test_every_language_has_every_message():
    assert MESSAGES["ko"].keys() == MESSAGES["en"].keys()


LONG_DOC = "# T\n\n## A\n\n## B\n\n## C\n\n[x](./other.md)\n"


def test_korean_page_translates_the_chrome_but_not_the_document():
    page = render_markdown_page("a.md", LONG_DOC, locale="ko")
    assert "<html lang='ko'>" in page
    assert "읽기 전용 · DocSanctum" in page
    assert "<summary>목차</summary>" in page
    assert 'title="공유되지 않은 문서예요. DocSanctum에서 열어 주세요."' in page
    assert "Contents" not in page


def test_english_is_the_default():
    page = render_markdown_page("a.md", LONG_DOC)
    assert "<html lang='en'>" in page
    assert "Read-only · DocSanctum" in page
    assert "<summary>Contents</summary>" in page


def test_notice_page_carries_its_language():
    assert "<html lang='ko'>" in render_notice_page("만료된 링크입니다.", "ko")
