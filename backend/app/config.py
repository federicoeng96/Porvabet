from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://porvabet:porvabet_dev@localhost:5432/porvabet"

    # Provider configuration — populated only when the user has obtained real credentials.
    # Absence of a key must degrade gracefully (provider reports itself unavailable),
    # never fall back to fabricated data.
    api_football_key: str | None = None

    # football-data.org (category A — see DATA_SOURCES.md): free key from the
    # user's own account, used only to fetch the next matchday's fixtures for
    # Premier League/Serie A. Absence means FootballDataOrgFixtureProvider
    # degrades to is_available()=False, never a fabricated fixture.
    #
    # Also accepts FOOTBALL_DATA_API_KEY (without "_ORG"): this exact naming
    # mismatch was the real root cause of the key appearing "missing" across
    # several sessions even after the user set it — the env var was present
    # under the shorter name the whole time, but pydantic-settings only reads
    # the field's own name by default. Kept as a fallback rather than renamed
    # everywhere, since "_ORG" still matters to disambiguate from the
    # unrelated football-data.co.uk CSV source used elsewhere in this project.
    football_data_org_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("FOOTBALL_DATA_ORG_API_KEY", "FOOTBALL_DATA_API_KEY"),
    )

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
