import time

import httpx

from app.config import settings


class KisError(RuntimeError):
    """KIS API 가 오류 응답을 반환했을 때."""


# (access_token, 만료 epoch초) — 모듈 수준 캐시. 테스트는 clear_token_cache() 로 초기화.
_cached_token: tuple[str, float] | None = None


def clear_token_cache() -> None:
    global _cached_token
    _cached_token = None


async def get_access_token() -> str:
    global _cached_token
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
    expires_in = float(data.get("expires_in", 0) or 0)
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
        "price": int(output.get("stck_prpr", 0) or 0),
        "change": int(output.get("prdy_vrss", 0) or 0),
        "change_rate": float(output.get("prdy_ctrt", 0) or 0),
        "volume": int(output.get("acml_vol", 0) or 0),
    }
