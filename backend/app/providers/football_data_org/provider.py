"""Fixture/calendar provider for football-data.org (DATA_SOURCES.md category
A_UNRESTRICTED — official third-party football data API, not a scraped site).

**Why this project needs a dedicated fixture source at all.** Every other
match-producing path in this codebase (`ingest_historical_match`) only ever
creates a `Match` row for an ALREADY-PLAYED fixture, since football-data.co.uk
(this project's primary source) only ever publishes historical CSVs — it has
never been a calendar of upcoming fixtures. Verified via a direct DB query
this session: 7,600 real matches ingested, 0 with a future kickoff. Without a
real fixture source, there is no "next matchday" row to ever run
`run_analysis_for_match` against for an un-played match — this provider closes
that gap.

**Why football-data.org, not diretta.it.** An earlier plan for this same gap
considered diretta.it (already an accepted, user-authorized ToS override for
*odds* — see `app.providers.betson_diretta`), but diretta.it's match/fixture
data — like its odds — is loaded by client-side JS after the page loads, not
present in the server-rendered HTML (verified live this session: fetching
`https://www.diretta.it/calcio/inghilterra/premier-league/` directly returns a
783KB page shell with zero `event__match`/`event__participant`-class match
containers; the real data comes from a GraphQL feed at `400.ds.lsapp.eu` whose
request-signing scheme is undocumented anywhere reachable this session) — the
exact same blocker already documented for Betson's odds. Building a fixture
scraper on an unverified guess of that feed's signing scheme would be exactly
the "invented endpoint" failure mode this project avoids. football-data.org is
a purpose-built, documented REST API for this exact use case instead.

**Verified live this session, not assumed:**
- Base URL `https://api.football-data.org/v4` — real, reachable from this
  sandbox (unlike Betfair, which is geo/anti-fraud-blocked here): an
  unauthenticated call to the free `/v4/areas/2072` endpoint returned a real
  200 JSON body; an authenticated call with a syntactically-invalid token
  returned `400 {"message": "Your API token is invalid."}` (not a network
  block), confirming the only thing missing is a real registered key.
- Auth: header `X-Auth-Token: <key>` (confirmed both from the API's own
  error-message wording and from football-data.org's own documentation page,
  `/documentation/api`, which explicitly lists `X-Auth-Token` as the request
  header carrying "Your authentication token").
- Real endpoint used here, copied verbatim from a live `curl` example on the
  current (v4, migrated 2022-05-20) docs page,
  `https://www.football-data.org/documentation/quickstart`:
  `GET /v4/competitions/{code}/matches?matchday=N`. Competition codes
  confirmed from the same page's own examples: `PL` (Premier League), `SA`
  (Serie A) — this project's two competitions.
- `GET /v4/competitions/{code}` returns `currentSeason.currentMatchday`
  (confirmed via a live documented example response for `PL`, shape:
  `{"currentSeason": {"startDate": "...", "currentMatchday": 37, ...}}`) —
  used here to find the actual next matchday to fetch, rather than guessing a
  number.
- Free tier confirmed (via the public https://www.football-data.org/pricing
  page) to include both Premier League and Serie A among its 12 free
  competitions, with "Fixtures, Schedules delayed" and a 10-calls/minute
  budget — this project's `RateLimiter(10, 60)` below matches that published
  figure exactly, not a made-up conservative guess like some other providers
  in this codebase.
- **No public Terms of Service page was found** (`/terms`, `/terms-of-service`,
  `/legal`, `/tos` all returned 404 this session) — same honest caveat this
  project already applies to API-Football (see
  `app.providers.api_football.provider`): unlike a scraped consumer website,
  this API's entire purpose is third-party programmatic access, so there is
  no ToS-interpretation risk to weigh the way there is for e.g. diretta.it —
  but the absence of a page to quote should not be read as "verified clean",
  only as "no prohibition was found to weigh against".

**Requires a free API key** (`FOOTBALL_DATA_ORG_API_KEY` env var /
`settings.football_data_org_api_key`) that the user must obtain via free
registration at football-data.org (same one-time manual step already
required for Betfair's App Key and, optionally, API-Football's key) — no
account/key was available in this session, so this has been tested against a
fake client built from the real, verified JSON shapes above, never against
live data. `is_available()` returns False without a key; nothing here ever
fabricates a fixture.

**Scope, per explicit instruction**: only the *next* matchday per
competition — not a full season calendar. `currentMatchday` from
`/v4/competitions/{code}` already gives exactly that reference point; no
season-long backfill is attempted here.
"""

from datetime import datetime

import httpx

from app.config import settings
from app.core.rate_limiter import RateLimiter
from app.models.enums import DataSourceCategory
from app.providers.base.dto import HistoricalMatchRecord, UpcomingFixtureRecord
from app.providers.base.sports_data_provider import SportsDataProvider

BASE_URL = "https://api.football-data.org/v4"

# football-data.org's own competition codes (confirmed live from its current
# API docs, not guessed) for this project's two competitions.
COMPETITION_TO_CODE = {
    "EPL": "PL",
    "SERIE_A": "SA",
}

# "Not yet played, kickoff known or provisionally known" — football-data.org's
# own status vocabulary (confirmed from the real v4 match JSON shape above).
# FINISHED/IN_PLAY/PAUSED/POSTPONED/SUSPENDED/CANCELLED are all excluded.
UPCOMING_STATUSES = {"SCHEDULED", "TIMED"}


class FootballDataOrgApiKeyMissingError(RuntimeError):
    pass


def _season_label_from_start_date(start_date: str) -> str:
    """football-data.org gives the real season boundary (`currentSeason.startDate`,
    e.g. "2021-08-13") — derived from that real value, never guessed from a
    caller-supplied label, matching this project's "2024/2025" convention."""
    year = int(start_date[:4])
    return f"{year}/{year + 1}"


class FootballDataOrgFixtureProvider(SportsDataProvider):
    source_key = "football_data_org"
    category = DataSourceCategory.A_UNRESTRICTED

    def __init__(self, api_key: str | None = None, http_client: httpx.Client | None = None) -> None:
        self._api_key = api_key or settings.football_data_org_api_key
        self._client = http_client or httpx.Client(base_url=BASE_URL, timeout=20.0)
        # Matches the free tier's own published 10 calls/minute budget (see
        # module docstring) — not a conservative guess.
        self._rate_limiter = RateLimiter(max_calls=10, period_seconds=60.0)

    def is_available(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        return {"X-Auth-Token": self._api_key or ""}

    def _require_key(self) -> None:
        if not self.is_available():
            raise FootballDataOrgApiKeyMissingError(
                "FootballDataOrgFixtureProvider requires football_data_org_api_key "
                "(env var FOOTBALL_DATA_ORG_API_KEY) — a free key from your own "
                "football-data.org account (Get Started at football-data.org). "
                "See DATA_SOURCES.md for how to obtain one."
            )

    def get_current_matchday(self, competition_code: str) -> int:
        """The real current matchday for a competition, per
        `/v4/competitions/{code}` -> `currentSeason.currentMatchday` — never
        guessed or hardcoded."""
        self._require_key()
        code = COMPETITION_TO_CODE[competition_code]
        self._rate_limiter.acquire()
        response = self._client.get(f"/competitions/{code}", headers=self._headers())
        response.raise_for_status()
        payload = response.json()
        return payload["currentSeason"]["currentMatchday"]

    def get_next_matchday_fixtures(self, competition_code: str) -> list[UpcomingFixtureRecord]:
        """The next (current) matchday's not-yet-played fixtures for one
        competition — the only scope this provider is asked to cover (see
        module docstring). Returns an empty list, never a fabricated fixture,
        if every match in that matchday has already been played/postponed."""
        matchday = self.get_current_matchday(competition_code)
        code = COMPETITION_TO_CODE[competition_code]

        self._rate_limiter.acquire()
        response = self._client.get(
            f"/competitions/{code}/matches",
            params={"matchday": matchday},
            headers=self._headers(),
        )
        response.raise_for_status()
        payload = response.json()

        records = []
        for item in payload.get("matches", []):
            if item.get("status") not in UPCOMING_STATUSES:
                continue
            season_label = _season_label_from_start_date(item["season"]["startDate"])
            records.append(
                UpcomingFixtureRecord(
                    competition_code=competition_code,
                    season_label=season_label,
                    kickoff_utc=datetime.fromisoformat(item["utcDate"]),
                    home_team_name=item["homeTeam"]["name"],
                    away_team_name=item["awayTeam"]["name"],
                    external_ref=f"football_data_org:{item['id']}",
                )
            )
        return records

    # --- SportsDataProvider interface (see app.providers.base.sports_data_provider) ---

    def get_historical_matches(
        self, competition_code: str, season_label: str
    ) -> list[HistoricalMatchRecord]:
        # Out of scope for this provider in this project (football-data.co.uk
        # already covers historical results+odds — see DATA_SOURCES.md) —
        # never implemented speculatively for a use this project doesn't have.
        raise NotImplementedError(
            "FootballDataOrgFixtureProvider only implements fixtures "
            "(get_next_matchday_fixtures) in this project — historical results "
            "come from football-data.co.uk instead. See DATA_SOURCES.md."
        )

    def get_upcoming_fixtures(
        self, competition_code: str, season_label: str
    ) -> list[UpcomingFixtureRecord]:
        # This project's actual entry point is `get_next_matchday_fixtures`
        # (no season_label needed — football-data.org's own "current season"
        # concept already scopes it). This override just delegates so the
        # class still satisfies the base SportsDataProvider contract.
        return self.get_next_matchday_fixtures(competition_code)
