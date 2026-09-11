"""Real SportsDataProvider for understat.com (DATA_SOURCES.md category A).

understat.com has no public API; it embeds match/team/player xG data as
JSON-encoded strings inside `<script>` tags on its league pages, e.g.:

    https://understat.com/league/{league_slug}/{season_year}

with a line such as `var datesData = JSON.parse('\\x7B...')`. The payload is a
JavaScript string-escaped (hex/unicode-escaped) UTF-8 JSON document; the standard
decode is: take the matched string, decode it as `unicode_escape`, re-encode as
latin1 bytes, then decode those bytes as utf-8 (this two-step round trip is the
documented approach used by every open-source understat scraper, since the page
mixes literal `\\xHH` byte escapes with genuine UTF-8 multi-byte sequences).

This provider has not been exercised against the live site from within the current
sandboxed session (network-restricted); the embedded-script variable names and
encoding above are corroborated by multiple independent scraper implementations
but should be spot-checked against a live page fetch before relying on this in
production, since understat's page internals could drift without notice.

Understat provides xG/xA context, not full match results with all bookmaker odds,
so this provider is meant to be combined with football-data.co.uk (results/odds),
matched on team name + date — not used as a standalone results source.
"""

import json
import re
from datetime import UTC, datetime

import httpx

from app.models.enums import DataSourceCategory
from app.providers.base.dto import HistoricalMatchRecord
from app.providers.base.sports_data_provider import SportsDataProvider

BASE_URL = "https://understat.com"

COMPETITION_TO_SLUG = {
    "EPL": "EPL",
    "SERIE_A": "Serie_A",
}

_SCRIPT_VAR_PATTERN = re.compile(r"var\s+datesData\s*=\s*JSON\.parse\('(.*?)'\);", re.DOTALL)


class UnderstatProvider(SportsDataProvider):
    source_key = "understat"
    category = DataSourceCategory.A_UNRESTRICTED

    def __init__(self, http_client: httpx.Client | None = None, timeout_s: float = 20.0) -> None:
        self._client = http_client or httpx.Client(timeout=timeout_s, follow_redirects=True)

    def is_available(self) -> bool:
        return True

    def get_historical_matches(
        self, competition_code: str, season_label: str
    ) -> list[HistoricalMatchRecord]:
        if competition_code not in COMPETITION_TO_SLUG:
            raise ValueError(f"understat does not cover {competition_code!r}")
        slug = COMPETITION_TO_SLUG[competition_code]
        season_year = season_label.split("/")[0]
        url = f"{BASE_URL}/league/{slug}/{season_year}"
        response = self._client.get(url)
        response.raise_for_status()
        matches = self.parse_dates_data(response.text)

        records = []
        for m in matches:
            if not m.get("isResult"):
                continue  # skip not-yet-played fixtures
            records.append(
                HistoricalMatchRecord(
                    competition_code=competition_code,
                    season_label=season_label,
                    kickoff_utc=datetime.strptime(m["datetime"], "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=UTC
                    ),
                    home_team_name=m["h"]["title"],
                    away_team_name=m["a"]["title"],
                    home_goals_ft=int(m["goals"]["h"]),
                    away_goals_ft=int(m["goals"]["a"]),
                    home_goals_ht=None,
                    away_goals_ht=None,
                    external_ref=str(m["id"]),
                )
            )
        return records

    @staticmethod
    def parse_dates_data(html: str) -> list[dict]:
        match = _SCRIPT_VAR_PATTERN.search(html)
        if not match:
            raise ValueError("Could not locate 'datesData' script payload in understat HTML")
        raw = match.group(1)
        decoded = raw.encode("utf-8").decode("unicode_escape").encode("latin1").decode("utf8")
        return json.loads(decoded)

    def get_team_xg(self, team_understat_id: str, season_year: str) -> dict:
        """Fetch a team's per-match xG/xGA series, used as a feature input
        (opponent-adjusted attack/defense strength) alongside raw goals.
        Not wired into the vertical-slice ingestion yet — see ROADMAP.md."""
        raise NotImplementedError("Team xG page parsing planned for a later phase (see ROADMAP.md)")
