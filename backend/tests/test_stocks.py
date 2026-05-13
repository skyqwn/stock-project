import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

BASE = "https://openapivts.koreainvestment.com:29443"
TOKEN_URL = f"{BASE}/oauth2/tokenP"
PRICE_URL = f"{BASE}/uapi/domestic-stock/v1/quoting/inquire-price"


@pytest.fixture(autouse=True)
def _kis_creds(monkeypatch):
    monkeypatch.setattr(settings, "kis_app_key", "test-key")
    monkeypatch.setattr(settings, "kis_app_secret", "test-secret")
    monkeypatch.setattr(settings, "kis_base_url", BASE)


@respx.mock
def test_stock_price_endpoint_ok():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "abc", "expires_in": 86400})
    )
    respx.get(PRICE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "OK",
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
    client = TestClient(app)
    resp = client.get("/api/stocks/005930/price")
    assert resp.status_code == 200
    assert resp.json() == {
        "code": "005930",
        "name": "삼성전자",
        "price": 70000,
        "change": 1000,
        "change_rate": 1.45,
        "volume": 12345678,
    }


@respx.mock
def test_stock_price_endpoint_returns_502_on_kis_error():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "abc", "expires_in": 86400})
    )
    respx.get(PRICE_URL).mock(
        return_value=httpx.Response(200, json={"rt_cd": "1", "msg1": "조회할 자료가 없습니다."})
    )
    client = TestClient(app)
    resp = client.get("/api/stocks/000000/price")
    assert resp.status_code == 502
    assert "조회" in resp.json()["detail"]
