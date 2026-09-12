"""Real LineupProvider for Corriere dello Sport's "Probabili Formazioni" page
(DATA_SOURCES.md category B — personal use only, Serie A only).

**Verified in this session, real HTTP requests:**
`GET https://www.corrieredellosport.it/probabili-formazioni/calcio/serie-a`
returns a real, server-rendered (not JS-only) HTML page listing every Serie A
fixture of the upcoming matchday, each in a block tagged
`ProbabiliFormazioni_teamName__*` / `ProbabiliFormazioni_teamFormation__*` —
the formation div is present in the markup ahead of kickoff but empty until
the source (explicitly labelled "dati OPTA" on the page) actually knows the
team's shape, at which point it is filled with a string like `"4-3-3"`.
robots.txt (fetched live) does not disallow this path or the site's football
sections generally (only `/account/`, `/search`, a few CMS/test paths); the
site's own `llms.txt` (a voluntary machine-readable usage policy, fetched
live) explicitly authorizes "discovery, indexing guidance and informational
reference" to its public pages and only requires attribution — it prohibits
"model training, dataset creation, commercial redistribution, large-scale
extraction or automated republication" without a separate licence, none of
which this project does (single-user, non-commercial, reference lookups per
match, not bulk harvesting or redistribution). No clause anywhere on the
site (main ToS, checked live) reserves rights against text/data mining the
way Gazzetta dello Sport's does (see that section of DATA_SOURCES.md) — this
is a real, substantive difference between two outlets that might otherwise
look interchangeable, not an assumption.

**Known, explicit limitation — this source gives team formation only, not
player-level data.** The listing page never exposes individual player names
anywhere in this session's inspection; only the team-level formation shape
(e.g. "4-3-3") once the source has it. `player_names_starting` on every
`LineupProjectionRecord` this provider returns is therefore always `[]` — it
does **not** and must **not** be treated as informing player-prop markets,
"chi tira i rigori" or ballottaggio-level (starting XI battle) data. No
source audited in this session (Corriere dello Sport, Gazzetta dello Sport,
SOS Fanta, Sky Sport Italia) was found to expose that at both an acceptable
risk level and a reliably structured (non-prose, non-NLP) format — see
DATA_SOURCES.md for the full audit, including why forcing a prose parser
against a free-text lineup article was rejected as fragile rather than
attempted.

A record is only returned once the source itself has populated a
non-empty formation for that team — before that, this provider returns
nothing for the match, exactly as if it did not exist, never a placeholder
or a guess.
"""

import re
from datetime import UTC, datetime

import httpx

from app.core.rate_limiter import RateLimiter
from app.models.enums import DataSourceCategory
from app.providers.base.dto import LineupProjectionRecord
from app.providers.base.lineup_provider import LineupProvider

SERIE_A_URL = "https://www.corrieredellosport.it/probabili-formazioni/calcio/serie-a"

_TIME_PATTERN = re.compile(
    r'<time class="ProbabiliFormazioni_day__[^"]*">(.*?)</time>', re.DOTALL
)
_TEAM_NAME_PATTERN = re.compile(
    r'<div class="ProbabiliFormazioni_teamName__[^"]*">([^<]*)</div>'
)
_TEAM_FORMATION_PATTERN = re.compile(
    r'<div class="ProbabiliFormazioni_teamFormation__[^"]*">([^<]*)</div>'
)
_HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)


class _ParsedFixture:
    def __init__(self, home_team: str, away_team: str, home_formation: str, away_formation: str):
        self.home_team = home_team
        self.away_team = away_team
        self.home_formation = home_formation
        self.away_formation = away_formation


def _parse_fixtures(html: str) -> list[_ParsedFixture]:
    fixtures = []
    for block in html.split('data-item="item-')[1:]:
        names = _TEAM_NAME_PATTERN.findall(block)
        formations = _TEAM_FORMATION_PATTERN.findall(block)
        if len(names) != 2 or len(formations) != 2:
            continue  # unrecognized block shape — skip rather than guess
        fixtures.append(
            _ParsedFixture(
                home_team=names[0].strip(),
                away_team=names[1].strip(),
                home_formation=formations[0].strip(),
                away_formation=formations[1].strip(),
            )
        )
    return fixtures


class CorriereDelloSportLineupProvider(LineupProvider):
    source_key = "corriere_dello_sport"
    category = DataSourceCategory.B_PERSONAL_USE_ONLY
    is_official_source = False

    def __init__(self, http_client: httpx.Client | None = None, timeout_s: float = 20.0) -> None:
        self._client = http_client or httpx.Client(
            timeout=timeout_s,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Porvabet-personal-use/1.0)"},
        )
        # No documented rate limit found for this source — conservative
        # self-imposed budget, same posture as fbref's documented one, to
        # avoid hammering a source that has no stated bot-traffic policy.
        self._rate_limiter = RateLimiter(max_calls=6, period_seconds=60.0)

    def is_available(self) -> bool:
        return True

    def get_probable_lineups(
        self, home_team_name: str, away_team_name: str, kickoff_utc_iso: str
    ) -> list[LineupProjectionRecord]:
        fixtures = self._fetch_serie_a_fixtures()
        home_lower = home_team_name.strip().lower()
        away_lower = away_team_name.strip().lower()

        match = next(
            (
                f
                for f in fixtures
                if f.home_team.lower() == home_lower and f.away_team.lower() == away_lower
            ),
            None,
        )
        if match is None:
            return []

        now = datetime.now(UTC)
        records = []
        if match.home_formation:
            records.append(
                LineupProjectionRecord(
                    team_name=match.home_team,
                    player_names_starting=[],
                    formation=match.home_formation,
                    is_official=False,
                    published_at=now,
                    source_key=self.source_key,
                )
            )
        if match.away_formation:
            records.append(
                LineupProjectionRecord(
                    team_name=match.away_team,
                    player_names_starting=[],
                    formation=match.away_formation,
                    is_official=False,
                    published_at=now,
                    source_key=self.source_key,
                )
            )
        return records

    def _fetch_serie_a_fixtures(self) -> list[_ParsedFixture]:
        self._rate_limiter.acquire()
        response = self._client.get(SERIE_A_URL)
        response.raise_for_status()
        html = _HTML_COMMENT_PATTERN.sub("", response.text)
        return _parse_fixtures(html)
