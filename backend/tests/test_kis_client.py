import httpx
import pytest
import respx

from app import kis_client
from app.config import settings

BASE = "https://openapivts.koreainvestment.com:29443"
TOKEN_URL = f"{BASE}/oauth2/tokenP"


@pytest.fixture(autouse=True)
def _kis_creds(monkeypatch):
    monkeypatch.setattr(settings, "kis_app_key", "test-key")
    monkeypatch.setattr(settings, "kis_app_secret", "test-secret")
    monkeypatch.setattr(settings, "kis_base_url", BASE)


@respx.mock
@pytest.mark.anyio
async def test_get_access_token_fetches_and_caches():
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "abc123", "token_type": "Bearer", "expires_in": 86400}
        )
    )
    token1 = await kis_client.get_access_token()
    token2 = await kis_client.get_access_token()
    assert token1 == "abc123"
    assert token2 == "abc123"
    assert route.call_count == 1  # 두 번째 호출은 캐시 사용


@respx.mock
@pytest.mark.anyio
async def test_get_access_token_raises_when_creds_missing(monkeypatch):
    monkeypatch.setattr(settings, "kis_app_key", "")
    with pytest.raises(kis_client.KisError):
        await kis_client.get_access_token()


PRICE_URL = f"{BASE}/uapi/domestic-stock/v1/quoting/inquire-price"


def _mock_token():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "abc123", "token_type": "Bearer", "expires_in": 86400}
        )
    )


@respx.mock
@pytest.mark.anyio
async def test_get_price_parses_output():
    _mock_token()
    respx.get(PRICE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "정상처리 되었습니다.",
                "output": {
                    "hts_kor_isnm": "삼성전자",
                    "stck_prpr": "70000",
                    "prdy_vrss": "1000",
                    "prdy_ctrt": "1.45",
                    "acml_vol": "12345678",
                },
            },
        )
    )
    result = await kis_client.get_price("005930")
    assert result == {
        "code": "005930",
        "name": "삼성전자",
        "price": 70000,
        "change": 1000,
        "change_rate": 1.45,
        "volume": 12345678,
    }


@respx.mock
@pytest.mark.anyio
async def test_get_price_raises_on_error_rt_cd():
    _mock_token()
    respx.get(PRICE_URL).mock(
        return_value=httpx.Response(200, json={"rt_cd": "1", "msg1": "조회할 자료가 없습니다."})
    )
    with pytest.raises(kis_client.KisError):
        await kis_client.get_price("000000")


@respx.mock
@pytest.mark.anyio
async def test_get_access_token_defaults_expiry_when_missing():
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok"})
    )
    token1 = await kis_client.get_access_token()
    token2 = await kis_client.get_access_token()
    assert token1 == "tok"
    assert token2 == "tok"
    assert route.call_count == 1  # 누락된 expires_in 도 ~24h 로 캐시 → 재요청 없음


@respx.mock
@pytest.mark.anyio
async def test_get_price_raises_kis_error_on_bad_number():
    _mock_token()
    respx.get(PRICE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "OK",
                "output": {
                    "hts_kor_isnm": "X",
                    "stck_prpr": "not-a-number",
                    "prdy_vrss": "0",
                    "prdy_ctrt": "0",
                    "acml_vol": "0",
                },
            },
        )
    )
    with pytest.raises(kis_client.KisError):
        await kis_client.get_price("000000")


@respx.mock
@pytest.mark.anyio
async def test_get_price_parses_decimal_price():
    _mock_token()
    respx.get(PRICE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "정상처리 되었습니다.",
                "output": {
                    "hts_kor_isnm": "삼성전자",
                    "stck_prpr": "70000.0",
                    "prdy_vrss": "1000",
                    "prdy_ctrt": "1.45",
                    "acml_vol": "12345678",
                },
            },
        )
    )
    result = await kis_client.get_price("005930")
    assert result["price"] == 70000
