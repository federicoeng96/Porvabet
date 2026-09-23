"""Tests TheOddsApiOddsProvider's request-building/response-parsing logic
against an `httpx.MockTransport` built from the exact JSON response shape
documented at the-odds-api.com/liveapi/guides/v4/ (verified this session by
reading that page directly — see the provider module's docstring) — never
against the live API, since no free API key was available in this session
(getting one requires registering an account, which needs a real inbox this
session does not have).
"""


import httpx

from app.models.enums import DataSourceCategory
from app.providers.the_odds_api.provider import (
    BASE_URL,
    H2H_MARKET_LABEL,
    TOTALS_MARKET_LABEL,
    TheOddsApiOddsProvider,
)

KICKOFF_ISO = "2026-09-26T14:00:00Z"

# Real response shape for GET /v4/sports/{sport}/odds — same structure
# documented for every sport, adapted here to a soccer h2h+totals example
# (draw outcome for h2h, 2.5 line for totals) per the-odds-api.com's own docs.
EPL_EVENTS_RESPONSE = [
    {
        "id": "abc123",
        "sport_key": "soccer_epl",
        "commence_time": KICKOFF_ISO,
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "bookmakers": [
            {
                "key": "bet365",
                "title": "Bet365",
                "last_update": "2026-09-25T10:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Arsenal", "price": 1.9},
                            {"name": "Chelsea", "price": 4.2},
                            {"name": "Draw", "price": 3.6},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 1.85, "point": 2.5},
                            {"name": "Under", "price": 1.95, "point": 2.5},
                        ],
                    },
                ],
            },
            {
                "key": "betfair_ex_uk",
                "title": "Betfair Exchange (UK)",
                "last_update": "2026-09-25T10:00:05Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Arsenal", "price": 1.92},
                            {"name": "Chelsea", "price": 4.3},
                            {"name": "Draw", "price": 3.65},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 1.87, "point": 2.5},
                            {"name": "Under", "price": 1.97, "point": 2.5},
                        ],
                    },
                ],
            },
        ],
    },
    {
        "id": "def456",
        "sport_key": "soccer_epl",
        "commence_time": "2026-09-27T16:30:00Z",
        "home_team": "Newcastle United",
        "away_team": "Fulham",
        "bookmakers": [],  # no bookmaker data at all — must not crash, must return nothing
    },
]

SERIE_A_EVENTS_RESPONSE = [
    {
        "id": "ghi789",
        "sport_key": "soccer_italy_serie_a",
        "commence_time": "2026-09-28T18:45:00Z",
        "home_team": "Napoli",
        "away_team": "Bologna",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "last_update": "2026-09-25T10:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Napoli", "price": 1.75},
                            {"name": "Bologna", "price": 4.9},
                            {"name": "Draw", "price": 3.8},
                        ],
                    }
                ],
            }
        ],
    }
]


def _fake_client(expected_key: str = "real-test-key", calls: list | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        assert request.url.params["apiKey"] == expected_key
        assert request.url.params["oddsFormat"] == "decimal"
        if "/sports/soccer_epl/odds" in str(request.url):
            return httpx.Response(200, json=EPL_EVENTS_RESPONSE)
        if "/sports/soccer_italy_serie_a/odds" in str(request.url):
            return httpx.Response(200, json=SERIE_A_EVENTS_RESPONSE)
        return httpx.Response(404, json={"message": "not found in this fake"})

    return httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))


def test_category_is_commercial_aggregator():
    provider = TheOddsApiOddsProvider(api_key="k", http_client=_fake_client())
    assert provider.category == DataSourceCategory.E_COMMERCIAL_AGGREGATOR_API


def test_is_available_false_without_api_key():
    provider = TheOddsApiOddsProvider(api_key=None, http_client=_fake_client())
    assert provider.is_available() is False
    assert provider.get_odds_for_match("Arsenal", "Chelsea", KICKOFF_ISO) == []


def test_prefers_betfair_exchange_over_other_bookmakers():
    """Both bet365 and betfair_ex_uk have prices for Arsenal v Chelsea —
    the preference order must pick Betfair Exchange, labelled distinctly
    from a direct BetfairExchangeOddsProvider quote."""
    provider = TheOddsApiOddsProvider(api_key="real-test-key", http_client=_fake_client())
    records = provider.get_odds_for_match("Arsenal", "Chelsea", KICKOFF_ISO)

    assert records, "expected real records for Arsenal v Chelsea"
    assert all("Betfair Exchange via The Odds API" in r.bookmaker for r in records)
    assert "diretto" in records[0].bookmaker  # must not be confused with a direct Betfair quote

    home = next(r for r in records if r.market_label == H2H_MARKET_LABEL and r.outcome_code == "HOME")
    assert home.decimal_odds == 1.92  # the betfair_ex_uk price, not bet365's 1.9
    draw = next(r for r in records if r.market_label == H2H_MARKET_LABEL and r.outcome_code == "DRAW")
    assert draw.decimal_odds == 3.65
    away = next(r for r in records if r.market_label == H2H_MARKET_LABEL and r.outcome_code == "AWAY")
    assert away.decimal_odds == 4.3

    over = next(r for r in records if r.market_label == TOTALS_MARKET_LABEL and r.outcome_code == "OVER")
    assert over.decimal_odds == 1.87
    under = next(r for r in records if r.market_label == TOTALS_MARKET_LABEL and r.outcome_code == "UNDER")
    assert under.decimal_odds == 1.97


def test_falls_back_to_next_preferred_bookmaker_when_betfair_absent():
    """Napoli v Bologna only has Pinnacle in the fake response — must use it
    and label it as such, not silently claim it's Betfair."""
    provider = TheOddsApiOddsProvider(api_key="real-test-key", http_client=_fake_client())
    records = provider.get_odds_for_match("Napoli", "Bologna", "2026-09-28T18:45:00Z")

    assert records
    assert all(r.bookmaker == "Pinnacle via The Odds API" for r in records)
    home = next(r for r in records if r.outcome_code == "HOME")
    assert home.decimal_odds == 1.75


def test_returns_nothing_for_event_with_no_bookmaker_data():
    provider = TheOddsApiOddsProvider(api_key="real-test-key", http_client=_fake_client())
    records = provider.get_odds_for_match("Newcastle United", "Fulham", "2026-09-27T16:30:00Z")
    assert records == []


def test_returns_nothing_for_unknown_fixture_without_crashing():
    provider = TheOddsApiOddsProvider(api_key="real-test-key", http_client=_fake_client())
    records = provider.get_odds_for_match("Some Team", "Another Team", KICKOFF_ISO)
    assert records == []


def test_caches_events_per_sport_key_across_calls():
    """The whole point of the cache (see module docstring "credit budget"):
    refreshing many matches in one batch must not re-fetch the same
    sport_key's events once per match."""
    calls: list = []
    provider = TheOddsApiOddsProvider(api_key="real-test-key", http_client=_fake_client(calls=calls))

    provider.get_odds_for_match("Arsenal", "Chelsea", KICKOFF_ISO)
    provider.get_odds_for_match("Newcastle United", "Fulham", "2026-09-27T16:30:00Z")
    provider.get_odds_for_match("Napoli", "Bologna", "2026-09-28T18:45:00Z")

    epl_calls = [c for c in calls if "soccer_epl" in c]
    serie_a_calls = [c for c in calls if "soccer_italy_serie_a" in c]
    assert len(epl_calls) == 1, f"expected exactly one soccer_epl fetch, got {len(epl_calls)}: {epl_calls}"
    assert len(serie_a_calls) == 1, f"expected exactly one soccer_italy_serie_a fetch, got {len(serie_a_calls)}"


def test_checks_serie_a_only_after_epl_miss():
    """Napoli v Bologna is not in the EPL response — the provider must try
    soccer_italy_serie_a next rather than giving up after the first miss."""
    provider = TheOddsApiOddsProvider(api_key="real-test-key", http_client=_fake_client())
    records = provider.get_odds_for_match("Napoli", "Bologna", "2026-09-28T18:45:00Z")
    assert records
