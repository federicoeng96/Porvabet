from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://porvabet:porvabet_dev@localhost:5432/porvabet"

    # Provider configuration — populated only when the user has obtained real credentials.
    # Absence of a key must degrade gracefully (provider reports itself unavailable),
    # never fall back to fabricated data.
    api_football_key: str | None = None

    cors_allow_origins: list[str] = ["http://localhost:3000"]

    env: str = "development"


settings = Settings()
