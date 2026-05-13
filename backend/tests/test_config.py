from app.config import Settings


def test_default_base_url_is_paper_trading():
    s = Settings(_env_file=None)
    assert s.kis_base_url == "https://openapivts.koreainvestment.com:29443"
    assert s.kis_app_key == ""
    assert s.kis_app_secret == ""
    assert s.kis_account == ""
