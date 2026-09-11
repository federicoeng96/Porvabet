"""Real SportsDataProvider for API-Football (api-football.com / api-sports.io v3).

DATA_SOURCES.md category A, but with caveats: this session could not directly read
api-football.com's current pricing/ToS pages (network-restricted sandbox), so the
free-tier request-per-day limit, included endpoints and free-tier historical depth
are NOT independently verified here — treat them as needing a human check of
https://www.api-football.com/pricing and /documentation-v3 before depending on them
for anything commercial. What *is* solid: the v3 REST API surface below (base URL,
auth header, endpoint paths/params) is the long-stable, publicly documented API
shape used by this provider.

Requires an API key (`API_FOOTBALL_KEY` env var / `settings.api_football_key`).
Without one, `is_available()` returns False and ingestion must skip this provider
rather than inventing fixtures.
"""

from datetime import UTC, datetime

import httpx

from app.config import settings
from app.models.enums import DataSourceCategory
from app.providers.base.dto import HistoricalMatchRecord, UpcomingFixtureRecord
from app.providers.base.sports_data_provider import SportsDataProvider

BASE_URL = "https://v3.football.api-sports.io"

# API-Football's own numeric league ids (stable, documented at /leagues).
COMPETITION_TO_LEAGUE_ID = {
    "EPL": 39,
    "SERIE_A": 135,
}


class ApiFootballProvider(SportsDataProvider):
    source_key = "api_football"
    category = DataSourceCategory.A_UNRESTRICTED

    def __init__(self, http_client: httpx.Client | None = None, timeout_s: float = 20.0) -> None:
        self._client = http_client or httpx.Client(
            base_url=BASE_URL,
            timeout=timeout_s,
            headers={"x-apisports-key": settings.api_football_key or ""},
        )

    def is_available(self) -> bool:
        return bool(settings.api_football_key)

    def get_historical_matches(
        self, competition_code: str, season_label: str
    ) -> list[HistoricalMatchRecord]:
        if not self.is_available():
            raise RuntimeError(
                "API_FOOTBALL_KEY not configured; refusing to fabricate fixtures. "
                "Register a free key at api-football.com and set it in .env."
            )
        league_id = COMPETITION_TO_LEAGUE_ID[competition_code]
        season_year = int(season_label.split("/")[0])
        response = self._client.get(
            "/fixtures", params={"league": league_id, "season": season_year, "status": "FT"}
        )
        response.raise_for_status()
        payload = response.json()
        return [
            _to_historical_record(item, competition_code, season_label)
            for item in payload.get("response", [])
        ]

    def get_upcoming_fixtures(
        self, competition_code: str, season_label: str
    ) -> list[UpcomingFixtureRecord]:
        if not self.is_available():
            raise RuntimeError("API_FOOTBALL_KEY not configured")
        league_id = COMPETITION_TO_LEAGUE_ID[competition_code]
        season_year = int(season_label.split("/")[0])
        response = self._client.get(
            "/fixtures", params={"league": league_id, "season": season_year, "status": "NS"}
        )
        response.raise_for_status()
        payload = response.json()
        return [
            UpcomingFixtureRecord(
                competition_code=competition_code,
                season_label=season_label,
                kickoff_utc=datetime.fromisoformat(item["fixture"]["date"]).astimezone(UTC),
                home_team_name=item["teams"]["home"]["name"],
                away_team_name=item["teams"]["away"]["name"],
                external_ref=str(item["fixture"]["id"]),
            )
            for item in payload.get("response", [])
        ]


def _to_historical_record(
    item: dict, competition_code: str, season_label: str
) -> HistoricalMatchRecord:
    fixture, teams, goals, score = item["fixture"], item["teams"], item["goals"], item["score"]
    return HistoricalMatchRecord(
        competition_code=competition_code,
        season_label=season_label,
        kickoff_utc=datetime.fromisoformat(fixture["date"]).astimezone(UTC),
        home_team_name=teams["home"]["name"],
        away_team_name=teams["away"]["name"],
        home_goals_ft=goals["home"],
        away_goals_ft=goals["away"],
        home_goals_ht=score.get("halftime", {}).get("home"),
        away_goals_ht=score.get("halftime", {}).get("away"),
        referee_name=fixture.get("referee"),
        external_ref=str(fixture["id"]),
    )
