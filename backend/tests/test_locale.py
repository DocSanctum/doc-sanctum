from __future__ import annotations

from types import SimpleNamespace

import pytest
from backend.app.api import locale as locale_module

# --- FR-003, FR-004: IP-based locale default (KR -> ko, other/private -> en/unknown) ---


def _make_request(
    headers: dict[str, str] | None = None, client_host: str | None = None
):
    return SimpleNamespace(
        headers=headers or {},
        client=SimpleNamespace(host=client_host) if client_host is not None else None,
    )


@pytest.mark.asyncio
async def test_korean_ip_via_x_forwarded_for_resolves_to_ko():
    request = _make_request(headers={"x-forwarded-for": "1.201.0.1"})
    result = await locale_module.get_locale(request)
    assert result.locale == "ko"


@pytest.mark.asyncio
async def test_non_korean_ip_resolves_to_en():
    request = _make_request(headers={"x-forwarded-for": "8.8.8.8"})
    result = await locale_module.get_locale(request)
    assert result.locale == "en"


@pytest.mark.asyncio
async def test_private_ip_resolves_to_unknown():
    request = _make_request(headers={"x-forwarded-for": "192.168.1.10"})
    result = await locale_module.get_locale(request)
    assert result.locale == "unknown"


@pytest.mark.asyncio
async def test_falls_back_to_client_host_without_forwarded_for_header():
    request = _make_request(client_host="8.8.8.8")
    result = await locale_module.get_locale(request)
    assert result.locale == "en"


@pytest.mark.asyncio
async def test_no_ip_available_resolves_to_unknown():
    request = _make_request(client_host=None)
    result = await locale_module.get_locale(request)
    assert result.locale == "unknown"


@pytest.mark.asyncio
async def test_x_forwarded_for_uses_first_ip_in_chain():
    request = _make_request(headers={"x-forwarded-for": "1.201.0.1, 10.0.0.1"})
    result = await locale_module.get_locale(request)
    assert result.locale == "ko"
