import asyncio
import time

import httpx

from app.config import settings


class KisError(RuntimeError):
    """KIS API 가 오류 응답을 반환했을 때."""


# (access_token, 만료 epoch초) — 모듈 수준 캐시. 테스트는 clear_token_cache() 로 초기화.
_cached_token: tuple[str, float] | None = None

# 토큰 발급 동시성 가드 (KIS 토큰 발급은 ~1회/분 으로 제한됨).
_token_lock = asyncio.Lock()


def clear_token_cache() -> None:
    global _cached_token
    _cached_token = None


def _to_int(value) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        raise KisError(f"숫자 파싱 실패: {value!r}")


def _to_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        raise KisError(f"숫자 파싱 실패: {value!r}")


async def get_access_token() -> str:
    global _cached_token
    now = time.time()
    if _cached_token is not None and _cached_token[1] - 60 > now:
        return _cached_token[0]

    async with _token_lock:
        # 락 안에서 재확인 (double-checked locking) — 다른 코루틴이 이미 발급했을 수 있음.
        now = time.time()
        if _cached_token is not None and _cached_token[1] - 60 > now:
            return _cached_token[0]

        if not settings.kis_app_key or not settings.kis_app_secret:
            raise KisError("KIS_APP_KEY / KIS_APP_SECRET 환경변수가 설정되지 않았습니다.")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.kis_base_url}/oauth2/tokenP",
                json={
                    "grant_type": "client_credentials",
                    "appkey": settings.kis_app_key,
                    "appsecret": settings.kis_app_secret,
                },
            )
        if resp.status_code != 200:
            raise KisError(f"토큰 발급 실패: HTTP {resp.status_code} {resp.text}")
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise KisError(f"토큰 응답에 access_token 없음: {data}")
        expires_in = float(data.get("expires_in") or 86400)
        if expires_in <= 0:
            expires_in = 86400.0
        _cached_token = (token, now + expires_in)
        return token


async def get_price(code: str) -> dict:
    token = await get_access_token()
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": settings.kis_app_key,
        "appsecret": settings.kis_app_secret,
        "tr_id": "FHKST01010100",
        "custtype": "P",
    }
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.kis_base_url}/uapi/domestic-stock/v1/quoting/inquire-price",
            headers=headers,
            params=params,
        )
    if resp.status_code != 200:
        raise KisError(f"현재가 조회 실패: HTTP {resp.status_code} {resp.text}")
    data = resp.json()
    if data.get("rt_cd") != "0":
        raise KisError(f"현재가 조회 오류: {data.get('msg1', data)}")
    output = data.get("output") or {}
    return {
        "code": code,
        "name": output.get("hts_kor_isnm", ""),
        "price": _to_int(output.get("stck_prpr")),
        "change": _to_int(output.get("prdy_vrss")),
        "change_rate": _to_float(output.get("prdy_ctrt")),
        "volume": _to_int(output.get("acml_vol")),
    }
