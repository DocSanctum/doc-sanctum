"""Text shown on share pages, in the viewer's browser language.

Share pages are rendered on the server for teammates who never load the app,
so they pick English or Korean from the Accept-Language header instead of
the app's language setting.
"""

from __future__ import annotations

from typing import Literal

Locale = Literal["en", "ko"]
DEFAULT_LOCALE: Locale = "en"

MESSAGES: dict[Locale, dict[str, str]] = {
    "en": {
        "badge": "Read-only · DocSanctum",
        "contents": "Contents",
        "unshared_link": "This document is not shared. Open it in DocSanctum.",
        "root": (
            "This address only opens documents shared from DocSanctum. "
            "Open the full link you were sent, which includes /share/ and a code."
        ),
        "invalid": "This link is invalid or has been revoked.",
        "expired": "This link has expired.",
        "gone": "The shared document is no longer available.",
        "fetch_failed": "The document could not be fetched right now.",
        "decode_failed": "The shared document could not be decoded.",
    },
    "ko": {
        "badge": "읽기 전용 · DocSanctum",
        "contents": "목차",
        "unshared_link": "공유되지 않은 문서예요. DocSanctum에서 열어 주세요.",
        "root": (
            "이 주소에서는 DocSanctum으로 공유된 문서만 열 수 있습니다. "
            "받은 링크 전체(/share/와 코드가 포함된 주소)로 열어 주세요."
        ),
        "invalid": "잘못된 링크이거나 공유가 해제된 링크입니다.",
        "expired": "만료된 링크입니다.",
        "gone": "공유된 문서를 더 이상 찾을 수 없습니다.",
        "fetch_failed": "지금은 문서를 가져올 수 없어요. 잠시 후 다시 시도해 주세요.",
        "decode_failed": "공유된 문서를 읽을 수 없습니다.",
    },
}


def _quality(params: str) -> float:
    for param in params.split(";"):
        key, _, value = param.strip().partition("=")
        if key.strip() == "q":
            try:
                return float(value)
            except ValueError:
                return 0.0
    return 1.0


def pick_locale(accept_language: str | None) -> Locale:
    """Return the supported language the browser ranks highest."""
    best: Locale = DEFAULT_LOCALE
    best_quality = 0.0
    for part in (accept_language or "").split(","):
        tag, _, params = part.strip().partition(";")
        primary = tag.strip().lower().split("-")[0]
        quality = _quality(params)
        # A strictly higher weight is needed, so earlier entries win ties.
        if primary in ("en", "ko") and quality > best_quality:
            best, best_quality = ("ko" if primary == "ko" else "en"), quality
    return best


def t(locale: Locale, key: str) -> str:
    return MESSAGES[locale][key]
