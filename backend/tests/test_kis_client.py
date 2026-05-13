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
