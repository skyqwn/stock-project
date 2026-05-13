import pytest


@pytest.fixture(autouse=True)
def _reset_kis_token_cache():
    # 각 테스트 전후로 모듈 수준 토큰 캐시를 비운다.
    from app import kis_client

    kis_client.clear_token_cache()
    yield
    kis_client.clear_token_cache()
