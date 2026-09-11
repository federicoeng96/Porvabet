"""Provider-agnostic data transfer objects.

Providers never return ORM models directly — they return these plain dataclasses,
so the ingestion layer (which maps DTOs onto the DB schema, resolving/creating
Team/Player/etc. rows) is the only place that talks to SQLAlchemy. This keeps a
provider swappable without touching the database layer, per ARCHITECTURE.md.
"""

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class HistoricalMatchRecord:
    """One historical (already-played) match, as reported by a sports-data source."""

    competition_code: str  # "EPL" | "SERIE_A"
    season_label: str  # "2024/2025"
    kickoff_utc: datetime
    home_team_name: str
    away_team_name: str
    home_goals_ft: int
    away_goals_ft: int
    home_goals_ht: int | None
    away_goals_ht: int | None
    referee_name: str | None = None

    home_shots: int | None = None
    away_shots: int | None = None
    home_shots_on_target: int | None = None
    away_shots_on_target: int | None = None
    home_corners: int | None = None
    away_corners: int | None = None
    home_fouls: int | None = None
    away_fouls: int | None = None
    home_yellow_cards: int | None = None
    away_yellow_cards: int | None = None
    home_red_cards: int | None = None
    away_red_cards: int | None = None

    # Closing odds bundled with the result row (football-data.co.uk style), keyed by
    # bookmaker name -> {"H": x, "D": y, "A": z} for 1X2, plus optional totals/AH.
    closing_odds_1x2: dict[str, dict[str, float]] = field(default_factory=dict)
    closing_odds_over_under_2_5: dict[str, dict[str, float]] = field(default_factory=dict)

    external_ref: str | None = None  # provider-specific identifier for idempotent upserts


@dataclass(frozen=True)
class UpcomingFixtureRecord:
    """A scheduled, not-yet-played match."""

    competition_code: str
    season_label: str
    kickoff_utc: datetime
    home_team_name: str
    away_team_name: str
    external_ref: str | None = None


@dataclass(frozen=True)
class OddsQuoteRecord:
    bookmaker: str
    market_label: str  # e.g. "1X2", "Over/Under 2.5"
    outcome_code: str  # "HOME", "DRAW", "AWAY", "OVER", "UNDER"
    decimal_odds: float
    captured_at: datetime
    is_closing: bool = False


@dataclass(frozen=True)
class LineupProjectionRecord:
    """A probable/official lineup for one team, as reported by one source."""

    team_name: str
    player_names_starting: list[str]
    formation: str | None
    is_official: bool
    published_at: datetime
    source_key: str


@dataclass(frozen=True)
class NewsItemRecord:
    team_name: str | None
    player_name: str | None
    headline: str
    body: str | None
    published_at: datetime
    url: str | None
    source_key: str


@dataclass(frozen=True)
class WeatherForecastRecord:
    kickoff_utc: datetime
    temperature_c: float | None
    wind_kph: float | None
    precipitation_mm: float | None
    condition: str | None
    forecast_at: date
