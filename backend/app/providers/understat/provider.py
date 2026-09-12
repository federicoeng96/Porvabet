"""SportsDataProvider for understat.com (DATA_SOURCES.md category B —
**reclassified this session**, was previously A_UNRESTRICTED).

**Two real findings from this session, both from live network verification —
neither assumed from documentation:**

1. **The site's internal structure changed — fixed here.** This provider used
   to look for `var datesData = JSON.parse('...')` embedded in the league
   page's HTML (understat's old rendering approach). A live fetch in this
   session showed that variable is gone from
   `https://understat.com/league/{league}/{season}` — the page is now a thin
   shell that loads `js/league.min.js`, which itself calls
   `GET /getLeagueData/{league}/{season}` (relative to the league page) via
   jQuery `$.ajax`, using the `PHPSESSID` cookie set by the initial page load
   as its session. Verified end-to-end with real requests (EPL and Serie A,
   2023 season): visiting the league page first, then calling
   `getLeagueData/...` with a `Referer` header and the same cookie jar,
   returns the full real dataset (`teams`, `dates`, `players` keys) — same
   underlying data as before, different delivery mechanism. A single
   `httpx.Client` with `follow_redirects=True` naturally persists the session
   cookie across both calls, so `_fetch_league_data` below just does both
   requests on one client.

2. **`robots.txt` disallows everything — this provider is reclassified
   A → B.** `https://understat.com/robots.txt` is `User-agent: *` /
   `Disallow: /` — a full-site disallow, no exceptions, for any crawler. No
   published Terms of Service was found for understat.com (extensive search)
   giving a specific clause to point to, unlike WhoScored/SofaScore's named
   betting-platform clauses — the risk here is the robots.txt directive
   itself, which is why `LICENSE_RISK` below names a different reason.
   Context, not a license to ignore it: understat is described by independent
   sources as one of the last free sources of live xG data for these leagues,
   and long-standing, actively-maintained open-source scrapers exist for it
   (e.g. the `understatapi` PyPI package) with no observed pattern of active
   enforcement (unlike fbref's Cloudflare challenge or ePlay24's edge block).
   That context doesn't erase the robots.txt directive, so — same posture as
   WhoScored/SofaScore — this class requires an explicit, non-default
   acknowledgement to instantiate.

`get_team_match_tactical_stats` is new in this session: the source for real
`TacticalFeature` rows (ROADMAP.md item 5 — corners/cards market feature gaps
aside, this is xG/PPDA/deep-completions data for the Matchup Engine), pulled
from the same `getLeagueData` payload's per-team `history` arrays.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx

from app.models.enums import DataSourceCategory
from app.providers.base.dto import HistoricalMatchRecord
from app.providers.base.sports_data_provider import SportsDataProvider

BASE_URL = "https://understat.com"

COMPETITION_TO_SLUG = {
    "EPL": "EPL",
    "SERIE_A": "Serie_A",
}


class PersonalUseNotAcknowledgedError(RuntimeError):
    pass


@dataclass(frozen=True)
class TeamMatchTacticalStats:
    """One team's advanced stats for one match — a row here, resolved against
    the matching `Match`/`Team` by (team_name, match_date), becomes one or more
    `TacticalFeature` rows. Raw PPDA components (attacking/defensive event
    counts) are kept rather than a single pre-divided ratio, so a caller can
    decide how to aggregate across a rolling window without re-deriving them."""

    team_name: str
    match_date: date
    is_home: bool
    xg: float
    xga: float
    npxg: float
    npxga: float
    ppda_att: int
    ppda_def: int
    ppda_allowed_att: int
    ppda_allowed_def: int
    deep: int
    deep_allowed: int


class UnderstatProvider(SportsDataProvider):
    source_key = "understat"
    category = DataSourceCategory.B_PERSONAL_USE_ONLY
    # Distinct from WhoScored/SofaScore's flag: the risk here is a full-site
    # robots.txt disallow, not a specific betting-platform ToS clause (no
    # published ToS was found at all) — see module docstring point 2.
    LICENSE_RISK = "personal_use_only_robots_disallow_all"

    def __init__(
        self,
        http_client: httpx.Client | None = None,
        timeout_s: float = 20.0,
        acknowledge_personal_use_only: bool = False,
    ) -> None:
        if not acknowledge_personal_use_only:
            raise PersonalUseNotAcknowledgedError(
                "UnderstatProvider requires acknowledge_personal_use_only=True. "
                "understat.com's robots.txt disallows all automated access "
                "(Disallow: / for User-agent: *) — see this module's docstring "
                "and DATA_SOURCES.md before enabling it."
            )
        self._client = http_client or httpx.Client(timeout=timeout_s, follow_redirects=True)

    def is_available(self) -> bool:
        return True

    def get_historical_matches(
        self, competition_code: str, season_label: str
    ) -> list[HistoricalMatchRecord]:
        data = self._fetch_league_data(competition_code, season_label)
        records = []
        for m in data["dates"]:
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

    def get_team_match_tactical_stats(
        self, competition_code: str, season_label: str
    ) -> list[TeamMatchTacticalStats]:
        data = self._fetch_league_data(competition_code, season_label)
        out = []
        for team in data["teams"].values():
            for h in team["history"]:
                out.append(
                    TeamMatchTacticalStats(
                        team_name=team["title"],
                        match_date=datetime.strptime(h["date"], "%Y-%m-%d %H:%M:%S")
                        .replace(tzinfo=UTC)
                        .date(),
                        is_home=(h["h_a"] == "h"),
                        xg=float(h["xG"]),
                        xga=float(h["xGA"]),
                        npxg=float(h["npxG"]),
                        npxga=float(h["npxGA"]),
                        ppda_att=int(h["ppda"]["att"]),
                        ppda_def=int(h["ppda"]["def"]),
                        ppda_allowed_att=int(h["ppda_allowed"]["att"]),
                        ppda_allowed_def=int(h["ppda_allowed"]["def"]),
                        deep=int(h["deep"]),
                        deep_allowed=int(h["deep_allowed"]),
                    )
                )
        return out

    def _fetch_league_data(self, competition_code: str, season_label: str) -> dict:
        if competition_code not in COMPETITION_TO_SLUG:
            raise ValueError(f"understat does not cover {competition_code!r}")
        slug = COMPETITION_TO_SLUG[competition_code]
        season_year = season_label.split("/")[0]
        league_url = f"{BASE_URL}/league/{slug}/{season_year}"
        # Establishes the PHPSESSID cookie the AJAX endpoint below requires —
        # see module docstring point 1. Response content itself isn't needed.
        self._client.get(league_url)
        data_url = f"{BASE_URL}/getLeagueData/{slug}/{season_year}"
        response = self._client.get(
            data_url,
            headers={"Referer": league_url, "X-Requested-With": "XMLHttpRequest"},
        )
        response.raise_for_status()
        return json.loads(response.text)
