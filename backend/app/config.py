from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    kis_app_key: str = ""
    kis_app_secret: str = ""
    # 모의투자 도메인. 실거래는 https://openapi.koreainvestment.com:9443
    kis_base_url: str = "https://openapivts.koreainvestment.com:29443"
    kis_account: str = ""  # 모의투자 계좌번호 (현재가 조회엔 불필요, 추후 확장용)


settings = Settings()
