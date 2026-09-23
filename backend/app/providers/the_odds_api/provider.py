"""OddsProvider for The Odds API (`the-odds-api.com` — DATA_SOURCES.md
category `E_COMMERCIAL_AGGREGATOR_API`).

**Not the same company as `theoddsapi.com`.** Confusingly similar name, but
a genuinely different product researched separately in this session: the
hyphenated `the-odds-api.com` ("The Odds API") free "Starter" plan covers
all sports (soccer included, `soccer_epl`/`soccer_italy_serie_a` are real
sport keys) at 500 credits/month; the unhyphenated `theoddsapi.com` free
plan is NBA/MLB `h2h` only, no soccer — irrelevant to this project. Every
claim below is about the hyphenated domain, verified against its own
primary docs/pricing pages, not a competitor's marketing copy about it.

**Why category E, not D (`D_OFFICIAL_API_PERSONAL_ACCOUNT`, used for
Betfair).** D is the *original* source, accessed via the user's own account
with that source — Betfair is Betfair. This is a third-party commercial
product that resells/relays OTHER bookmakers' (including Betfair's own
Exchange) data as its own paid API business, under its own commercial ToS.
That ToS (`the-odds-api.com/terms-and-conditions.html`, read directly, not
summarized from a blog) explicitly permits this project's exact use —
"training statistical and machine learning models", "displaying our data in
a UI... including for commercial use", "research papers and analytical
dashboards" — and only prohibits reselling the raw data itself "as a
standalone data product", which this project never does.

**Free tier, verified from the provider's own pricing page, not assumed
from its name**: "Starter" plan, $0/month, 500 credits/month, no credit
card, "all sports"/"all betting markets", "most bookmakers" (paid tiers add
the rest — which specific ones are excluded on free is not documented
anywhere this session could reach). Credit cost per call is
`markets x regions` (e.g. 2 markets x 1 region = 2 credits); ONE call
returns odds for every upcoming fixture of a whole sport/league at once
(not per-fixture, unlike some competitors this session also evaluated —
see DATA_SOURCES.md "Categoria E" for the full comparison), so 20 real
fixtures across EPL+Serie A cost the same ~4 credits per refresh as 2
fixtures would (2 sport keys x 2 markets x 1 region). At 500 credits/month
that is roughly 125 full refreshes/month if every call fetches both
competitions — comfortably usable for periodic "AGGIORNA ANALISI" clicks,
unlike a per-fixture-request competitor evaluated the same session (~10-11
refreshes/month for 20 fixtures, not practically usable). The 10-minute
per-sport-key cache below (`_CACHE_TTL_SECONDS`) exists specifically to keep
a single batch analysis (many matches, one HTTP request) inside that ~4
credit budget instead of re-fetching once per match.

**Bookmaker selection within a match — preference order, not "whichever
appears first".** A single response can list several bookmakers per
fixture; this provider prefers, in order: `betfair_ex_uk`/`betfair_ex_eu`
(Betfair Exchange — the same *kind* of instrument this project already
trusts and labels distinctly everywhere else, see
`app/providers/betfair/provider.py`), then `pinnacle` (this project's own
established sharp-book preference for backtesting, see
`BOOKMAKER_PREFERENCE` in `app/backtest/runner.py`), then a couple of major
soft books as a last resort. **Whichever one was actually used is recorded
in the returned `bookmaker_name`, distinctly labelled "via The Odds API"
so it is never mistaken for a direct `BetfairExchangeOddsProvider` quote —
the two can differ slightly (different capture time, this provider's own
polling/caching latency added on top of Betfair's already-delayed feed)**,
exactly the labelling discipline the rest of this project already applies.

**Corners/cards — a real capability this project did not have from any
other source, but coverage is NOT independently verified live in this
session.** The Odds API documents dedicated soccer markets
(`alternate_totals_corners`, `alternate_totals_cards`,
`alternate_spreads_corners`, `alternate_spreads_cards`, `corners_1x2`) at
the same credit cost as core markets — but its own docs also say
"coverage of non-featured markets is currently limited to selected
bookmakers and sports, and expanding over time", so this provider does NOT
request them yet: wiring them in needs one real response confirming actual
EPL/Serie A coverage (not assumed from the market existing in general),
same rigor already applied to Betfair's own corners/cards audit. Left as a
documented next step (see DATA_SOURCES.md), not implemented blind.

**Not tested against the live API in this session.** This sandbox CAN
reach `the-odds-api.com` (unlike Betfair, verified — see DATA_SOURCES.md),
but obtaining a free API key requires registering an account (the
dashboard redirect observed during research strongly implies email
verification), which needs a real inbox this session does not have — same
situation as `API_FOOTBALL_KEY`/`FOOTBALL_DATA_ORG_API_KEY` before the user
supplied them. The request-building/response-parsing logic below is tested
against the exact JSON response shape documented at
`the-odds-api.com/liveapi/guides/v4/` (`tests/test_the_odds_api_provider.py`,
`httpx.MockTransport`), not against live data. A real end-to-end run needs
the user's own free key (see DATA_SOURCES.md for the registration steps)
from a machine that can reach `the-odds-api.com` — this sandbox can, so
this one (unlike Betfair) could in principle also be verified from here
once a key exists, not only from the user's own computer.

**Team-name matching is a best-effort substring match, not a verified alias
map.** Unlike `UNDERSTAT_TEAM_NAME_ALIASES`/`FOOTBALL_DATA_ORG_TEAM_NAME_ALIASES`
(`app/ingestion/match_ingestion.py`), there is no real observed The Odds API
response in this session to build a hand-curated alias table from — team
names returned by a live call may not match this project's canonical names
exactly for every club. A future session with a real key should compare
actual responses against `Team.name` and extend an alias map the same way,
rather than this best-effort matching silently staying wrong.
"""

import logging
import time
from datetime import UTC, datetime

import httpx

from app.config import settings
from app.core.rate_limiter import RateLimiter
from app.models.enums import DataSourceCategory
from app.providers.base.dto import OddsQuoteRecord
from app.providers.base.odds_provider import OddsProvider

logger = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4"

# The Odds API's own sport keys (stable, documented) for the two competitions
# this project covers.
COMPETITION_SPORT_KEYS = ["soccer_epl", "soccer_italy_serie_a"]

H2H_MARKET_KEY = "h2h"
H2H_MARKET_LABEL = "1X2 (The Odds API)"
TOTALS_MARKET_KEY = "totals"
TOTALS_MARKET_LABEL = "Over/Under 2.5 (The Odds API)"
TOTAL_GOALS_LINE = 2.5
MARKETS_PARAM = f"{H2H_MARKET_KEY},{TOTALS_MARKET_KEY}"
REGIONS_PARAM = "uk"  # betfair_ex_uk/pinnacle/bet365 all live in this region

# See module docstring "Bookmaker selection within a match". Order matters.
BOOKMAKER_KEY_PREFERENCE = ["betfair_ex_uk", "betfair_ex_eu", "pinnacle", "bet365", "unibet"]

BOOKMAKER_LABELS = {
    "betfair_ex_uk": "Betfair Exchange via The Odds API (non diretto, v. DATA_SOURCES.md)",
    "betfair_ex_eu": "Betfair Exchange via The Odds API (non diretto, v. DATA_SOURCES.md)",
    "pinnacle": "Pinnacle via The Odds API",
    "bet365": "Bet365 via The Odds API",
    "unibet": "Unibet via The Odds API",
}

# Conservative self-imposed pacing — no documented per-minute rate limit was
# found in this session's research for the free tier (only the 500
# credits/month total), so this only guards against bursting many calls
# back-to-back, not a real published API limit.
_RATE_LIMIT_MAX_CALLS = 10
_RATE_LIMIT_PERIOD_SECONDS = 60.0

# See module docstring "500 credits/month... roughly 125 full refreshes" —
# this cache is what keeps one batch analysis (many matches, one HTTP
# request to this backend) inside ~4 credits instead of ~4 x n_matches.
_CACHE_TTL_SECONDS = 600.0


class TheOddsApiOddsProvider(OddsProvider):
    source_key = "the_odds_api"
    category = DataSourceCategory.E_COMMERCIAL_AGGREGATOR_API
    bookmaker_name = "The Odds API (aggregatore commerciale, v. DATA_SOURCES.md)"

    def __init__(
        self,
        api_key: str | None = None,
        http_client: httpx.Client | None = None,
        timeout_s: float = 20.0,
    ) -> None:
        self._api_key = api_key or settings.the_odds_api_key
        self._client = http_client or httpx.Client(base_url=BASE_URL, timeout=timeout_s)
        self._rate_limiter = RateLimiter(
            max_calls=_RATE_LIMIT_MAX_CALLS, period_seconds=_RATE_LIMIT_PERIOD_SECONDS
        )
        # sport_key -> (fetched_at_monotonic, events_json)
        self._events_cache: dict[str, tuple[float, list[dict]]] = {}

    def is_available(self) -> bool:
        return bool(self._api_key)

    def get_odds_for_match(
        self, home_team_name: str, away_team_name: str, kickoff_utc_iso: str
    ) -> list[OddsQuoteRecord]:
        """The abstract interface does not pass a competition code (same
        constraint `BetfairExchangeOddsProvider` has), so both covered sport
        keys are checked and whichever one's events contain this fixture's
        teams wins — the per-sport-key cache above means this costs network
        calls only on a genuine cache miss, not once per match."""
        if not self.is_available():
            return []

        home_lower = home_team_name.strip().lower()
        away_lower = away_team_name.strip().lower()

        for sport_key in COMPETITION_SPORT_KEYS:
            events = self._get_events(sport_key)
            event = next(
                (
                    e
                    for e in events
                    if _names_match(e.get("home_team", ""), home_lower)
                    and _names_match(e.get("away_team", ""), away_lower)
                ),
                None,
            )
            if event is not None:
                return _to_odds_quote_records(event)
        return []

    def _get_events(self, sport_key: str) -> list[dict]:
        cached = self._events_cache.get(sport_key)
        now = time.monotonic()
        if cached is not None and (now - cached[0]) < _CACHE_TTL_SECONDS:
            return cached[1]

        self._rate_limiter.acquire()
        response = self._client.get(
            f"/sports/{sport_key}/odds",
            params={
                "apiKey": self._api_key,
                "regions": REGIONS_PARAM,
                "markets": MARKETS_PARAM,
                "oddsFormat": "decimal",
            },
        )
        response.raise_for_status()
        events = response.json()
        self._events_cache[sport_key] = (now, events)
        return events


def _names_match(api_team_name: str, expected_lower: str) -> bool:
    """Best-effort, case-insensitive comparison — see module docstring
    "Team-name matching is a best-effort substring match" for why there is
    no verified alias map yet."""
    candidate = api_team_name.strip().lower()
    return candidate == expected_lower or expected_lower in candidate or candidate in expected_lower


def _pick_bookmaker(bookmakers: list[dict]) -> dict | None:
    by_key = {b.get("key"): b for b in bookmakers}
    for key in BOOKMAKER_KEY_PREFERENCE:
        if key in by_key:
            return by_key[key]
    return None


def _to_odds_quote_records(event: dict) -> list[OddsQuoteRecord]:
    bookmaker = _pick_bookmaker(event.get("bookmakers", []))
    if bookmaker is None:
        return []  # none of the preferred bookmakers had a price for this fixture
    label = BOOKMAKER_LABELS.get(bookmaker.get("key"), f"{bookmaker.get('title', 'sconosciuto')} via The Odds API")
    home_team = event.get("home_team", "")
    away_team = event.get("away_team", "")
    now = datetime.now(UTC)

    records: list[OddsQuoteRecord] = []
    for market in bookmaker.get("markets", []):
        market_key = market.get("key")
        if market_key == H2H_MARKET_KEY:
            records += _h2h_records(market, home_team, away_team, label, now)
        elif market_key == TOTALS_MARKET_KEY:
            records += _totals_records(market, label, now)
    return records


def _h2h_records(market: dict, home_team: str, away_team: str, label: str, now: datetime) -> list[OddsQuoteRecord]:
    home_lower, away_lower = home_team.strip().lower(), away_team.strip().lower()
    records = []
    for outcome in market.get("outcomes", []):
        name_lower = outcome.get("name", "").strip().lower()
        if name_lower == home_lower:
            code = "HOME"
        elif name_lower == away_lower:
            code = "AWAY"
        elif name_lower == "draw":
            code = "DRAW"
        else:
            continue
        records.append(
            OddsQuoteRecord(
                bookmaker=label,
                market_label=H2H_MARKET_LABEL,
                outcome_code=code,
                decimal_odds=outcome["price"],
                captured_at=now,
                is_closing=False,
            )
        )
    return records


def _totals_records(market: dict, label: str, now: datetime) -> list[OddsQuoteRecord]:
    records = []
    for outcome in market.get("outcomes", []):
        if outcome.get("point") != TOTAL_GOALS_LINE:
            continue  # only the 2.5 line matches this project's TOTAL_GOALS market
        name_lower = outcome.get("name", "").strip().lower()
        if name_lower == "over":
            code = "OVER"
        elif name_lower == "under":
            code = "UNDER"
        else:
            continue
        records.append(
            OddsQuoteRecord(
                bookmaker=label,
                market_label=TOTALS_MARKET_LABEL,
                outcome_code=code,
                decimal_odds=outcome["price"],
                captured_at=now,
                is_closing=False,
            )
        )
    return records
