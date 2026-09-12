from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://porvabet:porvabet_dev@localhost:5432/porvabet"

    # Provider configuration — populated only when the user has obtained real credentials.
    # Absence of a key must degrade gracefully (provider reports itself unavailable),
    # never fall back to fabricated data.
    api_football_key: str | None = None

    # Betfair Exchange (official API, personal account — see DATA_SOURCES.md).
    # `betfair_app_key` must be a Delayed (free) Application Key — this project
    # never uses a Live App Key. All three optional; absence means
    # BetfairExchangeOddsProvider.is_available() returns False.
    betfair_app_key: str | None = None
    betfair_username: str | None = None
    betfair_password: str | None = None

    cors_allow_origins: list[str] = ["http://localhost:3000"]

    env: str = "development"


settings = Settings()
