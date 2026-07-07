from fastapi import APIRouter, Request
from geoip2fast import GeoIP2Fast  # type: ignore
from pydantic import BaseModel

router = APIRouter(tags=["locale"])

_geoip = GeoIP2Fast()


class LocaleResult(BaseModel):
    locale: str


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.get("/locale", response_model=LocaleResult)
async def get_locale(request: Request) -> LocaleResult:
    ip = _client_ip(request)
    if not ip:
        return LocaleResult(locale="unknown")

    result = _geoip.lookup(ip)
    if result.is_private or result.country_code in ("", "--"):
        return LocaleResult(locale="unknown")

    return LocaleResult(locale="ko" if result.country_code == "KR" else "en")
