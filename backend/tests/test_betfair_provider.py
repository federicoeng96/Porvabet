"""Tests BetfairExchangeOddsProvider's request-building/response-parsing logic
against a fake client built from betfairlightweight's own real resource
classes (EventTypeResult, MarketCatalogue, MarketBook, etc., constructed with
the same camelCase field names Betfair's real JSON-RPC responses use) — never
against the live Betfair API. Real Betfair credentials are configured for
this project, but this sandboxed session's own network egress is blocked by
Betfair/Cloudflare itself (see the provider module's docstring and
DATA_SOURCES.md) — a live end-to-end run must happen from an unblocked
network (RUNNING_LOCALLY.md), not from this test suite.
"""

import pytest
from betfairlightweight.resources.bettingresources import (
    EventTypeResult,
    MarketBook,
    MarketCatalogue,
    MarketTypeResult,
)

from app.models.enums import DataSourceCategory
from app.providers.betfair.provider import (
    BETFAIR_BOOKMAKER_LABEL,
    BetfairCredentialsMissingError,
    BetfairExchangeOddsProvider,
)

KICKOFF_ISO = "2026-09-12T18:45:00Z"


class _FakeBetting:
    """`catalogues`/`books` are the plain single-market-type behavior every
    existing test uses (same response regardless of which market type was
    asked for). `catalogues_by_type`/`books_by_market_id` let a test give
    MATCH_ODDS and OVER_UNDER_25 genuinely different responses, keyed by the
    real request fields (`marketTypeCodes`, `market_ids`) — needed once this
    provider queries two market types per call."""

    def __init__(
        self,
        event_types,
        catalogues,
        books,
        catalogues_by_type=None,
        books_by_market_id=None,
        market_types=None,
    ):
        self._event_types = event_types
        self._catalogues = catalogues
        self._books = books
        self._catalogues_by_type = catalogues_by_type
        self._books_by_market_id = books_by_market_id
        self._market_types = market_types or []
        self.list_market_catalogue_calls = []
        self.list_market_book_calls = []
        self.list_market_types_calls = []

    def list_event_types(self, **kwargs):
        return self._event_types

    def list_market_catalogue(self, **kwargs):
        self.list_market_catalogue_calls.append(kwargs)
        if self._catalogues_by_type is not None:
            market_type = kwargs["filter"]["marketTypeCodes"][0]
            return self._catalogues_by_type.get(market_type, [])
        return self._catalogues

    def list_market_book(self, **kwargs):
        self.list_market_book_calls.append(kwargs)
        if self._books_by_market_id is not None:
            market_id = kwargs["market_ids"][0]
            return self._books_by_market_id.get(market_id, [])
        return self._books

    def list_market_types(self, **kwargs):
        self.list_market_types_calls.append(kwargs)
        return self._market_types


class _FakeClient:
    def __init__(self, event_types, catalogues, books):
        self.betting = _FakeBetting(event_types, catalogues, books)
        self.login_interactive_calls = 0
        self.keep_alive_calls = 0
        self.session_expired = False

    def login_interactive(self):
        self.login_interactive_calls += 1
        self.session_expired = False

    def keep_alive(self):
        self.keep_alive_calls += 1
        self.session_expired = False


def _soccer_event_types():
    return [
        EventTypeResult(eventType={"id": "1", "name": "Soccer"}, marketCount=1000),
        EventTypeResult(eventType={"id": "2", "name": "Tennis"}, marketCount=500),
    ]


def _match_odds_catalogue(market_id="1.123", event_name="Roma v Inter"):
    return [
        MarketCatalogue(
            marketId=market_id,
            marketName="Match Odds",
            totalMatched=10000.0,
            event={
                "id": "30000",
                "openDate": "2026-09-12T18:45:00.000Z",
                "timezone": "Europe/Rome",
                "name": event_name,
            },
            runners=[
                {"selectionId": 1, "runnerName": "Roma", "sortPriority": 1},
                {"selectionId": 2, "runnerName": "The Draw", "sortPriority": 2},
                {"selectionId": 3, "runnerName": "Inter", "sortPriority": 3},
            ],
        )
    ]


def _market_book_with_prices(market_id="1.123"):
    return [
        MarketBook(
            marketId=market_id,
            runners=[
                {
                    "selectionId": 1,
                    "status": "ACTIVE",
                    "handicap": 0.0,
                    "ex": {
                        "availableToBack": [{"price": 2.5, "size": 100.0}],
                        "availableToLay": [],
                        "tradedVolume": [],
                    },
                },
                {
                    "selectionId": 2,
                    "status": "ACTIVE",
                    "handicap": 0.0,
                    "ex": {
                        "availableToBack": [{"price": 3.4, "size": 50.0}],
                        "availableToLay": [],
                        "tradedVolume": [],
                    },
                },
                {
                    "selectionId": 3,
                    "status": "ACTIVE",
                    "handicap": 0.0,
                    "ex": {
                        "availableToBack": [{"price": 2.9, "size": 80.0}],
                        "availableToLay": [],
                        "tradedVolume": [],
                    },
                },
            ],
        )
    ]


def test_category_is_official_api_not_scraped_abc():
    provider = BetfairExchangeOddsProvider(
        app_key="k", username="u", password="p", client=_FakeClient([], [], [])
    )
    assert provider.category == DataSourceCategory.D_OFFICIAL_API_PERSONAL_ACCOUNT
    assert provider.bookmaker_name == BETFAIR_BOOKMAKER_LABEL


def _clear_real_betfair_settings(monkeypatch):
    """A constructor arg of `None` only means "fall back to settings" (see
    `__init__`: `app_key or settings.betfair_app_key`) — it does not force
    "no credentials". Once real BETFAIR_* env vars are configured (as they
    are for this project going forward), a bare `app_key=None` in a test
    would silently pick up the real key instead of testing the
    no-credentials path, so these "missing credential" tests must blank out
    `settings` explicitly rather than relying on the environment being empty."""
    monkeypatch.setattr("app.providers.betfair.provider.settings.betfair_app_key", None)
    monkeypatch.setattr("app.providers.betfair.provider.settings.betfair_username", None)
    monkeypatch.setattr("app.providers.betfair.provider.settings.betfair_password", None)


def test_is_available_requires_all_three_credentials(monkeypatch):
    _clear_real_betfair_settings(monkeypatch)
    assert BetfairExchangeOddsProvider(app_key=None, username="u", password="p").is_available() is False
    assert BetfairExchangeOddsProvider(app_key="k", username=None, password="p").is_available() is False
    assert BetfairExchangeOddsProvider(app_key="k", username="u", password=None).is_available() is False
    assert BetfairExchangeOddsProvider(app_key="k", username="u", password="p").is_available() is True


def test_raises_clear_error_without_credentials(monkeypatch):
    _clear_real_betfair_settings(monkeypatch)
    provider = BetfairExchangeOddsProvider(app_key=None, username=None, password=None)
    with pytest.raises(BetfairCredentialsMissingError):
        provider.get_odds_for_match("Roma", "Inter", KICKOFF_ISO)


def test_error_message_names_exact_env_vars_and_key_tier(monkeypatch):
    # The user must be able to fix this from the message alone, without
    # reading the source — not a cryptic/generic "missing config" error.
    _clear_real_betfair_settings(monkeypatch)
    provider = BetfairExchangeOddsProvider(app_key=None, username=None, password=None)
    with pytest.raises(BetfairCredentialsMissingError) as exc_info:
        provider.get_odds_for_match("Roma", "Inter", KICKOFF_ISO)
    message = str(exc_info.value)
    for expected in ("betfair_app_key", "betfair_username", "betfair_password", "Delayed"):
        assert expected in message


def test_reads_credentials_from_settings_env_vars_when_not_passed_explicitly(monkeypatch):
    # Verifies the actual env-var wiring (app.config.Settings), not just the
    # constructor-argument path exercised by every other test here.
    monkeypatch.setattr(
        "app.providers.betfair.provider.settings.betfair_app_key", "env-key"
    )
    monkeypatch.setattr(
        "app.providers.betfair.provider.settings.betfair_username", "env-user"
    )
    monkeypatch.setattr(
        "app.providers.betfair.provider.settings.betfair_password", "env-pass"
    )
    provider = BetfairExchangeOddsProvider()
    assert provider.is_available() is True


def test_returns_back_prices_labeled_as_betfair_exchange():
    fake_client = _FakeClient(
        _soccer_event_types(), _match_odds_catalogue(), _market_book_with_prices()
    )
    provider = BetfairExchangeOddsProvider(
        app_key="k", username="u", password="p", client=fake_client
    )

    records = provider.get_odds_for_match("Roma", "Inter", KICKOFF_ISO)

    assert fake_client.login_interactive_calls == 1  # never re-logged-in once cached
    by_outcome = {r.outcome_code: r for r in records}
    assert set(by_outcome) == {"HOME", "DRAW", "AWAY"}
    assert by_outcome["HOME"].decimal_odds == 2.5
    assert by_outcome["DRAW"].decimal_odds == 3.4
    assert by_outcome["AWAY"].decimal_odds == 2.9
    for r in records:
        assert r.bookmaker == BETFAIR_BOOKMAKER_LABEL
        assert "Betfair" in r.market_label
        assert r.is_closing is False


def test_reuses_cached_login_and_event_type_across_calls():
    fake_client = _FakeClient(
        _soccer_event_types(), _match_odds_catalogue(), _market_book_with_prices()
    )
    provider = BetfairExchangeOddsProvider(
        app_key="k", username="u", password="p", client=fake_client
    )

    provider.get_odds_for_match("Roma", "Inter", KICKOFF_ISO)
    provider.get_odds_for_match("Roma", "Inter", KICKOFF_ISO)

    assert fake_client.login_interactive_calls == 1
    # list_event_types is only hit once per process — soccer id is cached
    filter_used = fake_client.betting.list_market_catalogue_calls[0]["filter"]
    assert filter_used["eventTypeIds"] == ["1"]


def test_returns_empty_list_when_no_market_matches_team_names():
    fake_client = _FakeClient(
        _soccer_event_types(),
        _match_odds_catalogue(event_name="Napoli v Juventus"),
        _market_book_with_prices(),
    )
    provider = BetfairExchangeOddsProvider(
        app_key="k", username="u", password="p", client=fake_client
    )

    records = provider.get_odds_for_match("Roma", "Inter", KICKOFF_ISO)

    assert records == []


def test_returns_empty_list_when_no_catalogue_found():
    fake_client = _FakeClient(_soccer_event_types(), [], [])
    provider = BetfairExchangeOddsProvider(
        app_key="k", username="u", password="p", client=fake_client
    )

    records = provider.get_odds_for_match("Roma", "Inter", KICKOFF_ISO)

    assert records == []


def _over_under_25_catalogue(market_id="1.456", event_name="Roma v Inter"):
    return [
        MarketCatalogue(
            marketId=market_id,
            marketName="Over/Under 2.5 Goals",
            totalMatched=5000.0,
            event={
                "id": "30000",
                "openDate": "2026-09-12T18:45:00.000Z",
                "timezone": "Europe/Rome",
                "name": event_name,
            },
            runners=[
                {"selectionId": 11, "runnerName": "Under 2.5 Goals", "sortPriority": 1},
                {"selectionId": 12, "runnerName": "Over 2.5 Goals", "sortPriority": 2},
            ],
        )
    ]


def _over_under_25_book_with_prices(market_id="1.456"):
    return [
        MarketBook(
            marketId=market_id,
            runners=[
                {
                    "selectionId": 11,
                    "status": "ACTIVE",
                    "handicap": 0.0,
                    "ex": {
                        "availableToBack": [{"price": 1.95, "size": 60.0}],
                        "availableToLay": [],
                        "tradedVolume": [],
                    },
                },
                {
                    "selectionId": 12,
                    "status": "ACTIVE",
                    "handicap": 0.0,
                    "ex": {
                        "availableToBack": [{"price": 1.90, "size": 70.0}],
                        "availableToLay": [],
                        "tradedVolume": [],
                    },
                },
            ],
        )
    ]


def test_fetches_both_match_odds_and_over_under_25():
    fake_client = _FakeClient(
        _soccer_event_types(),
        catalogues=None,
        books=None,
    )
    fake_client.betting = _FakeBetting(
        _soccer_event_types(),
        catalogues=None,
        books=None,
        catalogues_by_type={
            "MATCH_ODDS": _match_odds_catalogue(),
            "OVER_UNDER_25": _over_under_25_catalogue(),
        },
        books_by_market_id={
            "1.123": _market_book_with_prices(),
            "1.456": _over_under_25_book_with_prices(),
        },
    )
    provider = BetfairExchangeOddsProvider(
        app_key="k", username="u", password="p", client=fake_client
    )

    records = provider.get_odds_for_match("Roma", "Inter", KICKOFF_ISO)

    by_outcome = {r.outcome_code: r for r in records}
    assert set(by_outcome) == {"HOME", "DRAW", "AWAY", "OVER", "UNDER"}
    assert by_outcome["OVER"].decimal_odds == 1.90
    assert by_outcome["UNDER"].decimal_odds == 1.95
    for code in ("OVER", "UNDER"):
        assert "Over/Under" in by_outcome[code].market_label
    # Both market types were actually requested, not just one reused twice.
    requested_types = {
        c["filter"]["marketTypeCodes"][0]
        for c in fake_client.betting.list_market_catalogue_calls
    }
    assert requested_types == {"MATCH_ODDS", "OVER_UNDER_25"}


def test_over_under_25_missing_does_not_block_match_odds():
    """If Betfair has no O/U 2.5 market for a fixture (e.g. too early, or an
    illiquid competition), MATCH_ODDS results must still come back — a
    missing market on one side is never allowed to suppress the other."""
    fake_client = _FakeClient(_soccer_event_types(), catalogues=None, books=None)
    fake_client.betting = _FakeBetting(
        _soccer_event_types(),
        catalogues=None,
        books=None,
        catalogues_by_type={"MATCH_ODDS": _match_odds_catalogue()},
        books_by_market_id={"1.123": _market_book_with_prices()},
    )
    provider = BetfairExchangeOddsProvider(
        app_key="k", username="u", password="p", client=fake_client
    )

    records = provider.get_odds_for_match("Roma", "Inter", KICKOFF_ISO)

    assert {r.outcome_code for r in records} == {"HOME", "DRAW", "AWAY"}


def test_uses_italian_locale_for_identity_endpoint(monkeypatch):
    captured_kwargs = {}

    class _CapturingAPIClient:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)
            self.session_expired = False

        def login_interactive(self):
            pass

    monkeypatch.setattr("app.providers.betfair.provider.APIClient", _CapturingAPIClient)
    provider = BetfairExchangeOddsProvider(app_key="k", username="u", password="p")
    provider._ensure_client()

    assert captured_kwargs["locale"] == "italy"


def test_ensure_client_renews_expired_session_via_keep_alive():
    fake_client = _FakeClient(_soccer_event_types(), [], [])
    provider = BetfairExchangeOddsProvider(
        app_key="k", username="u", password="p", client=fake_client
    )
    provider._ensure_client()
    assert fake_client.login_interactive_calls == 1

    fake_client.session_expired = True
    provider._ensure_client()

    assert fake_client.keep_alive_calls == 1
    assert fake_client.login_interactive_calls == 1  # renewed cheaply, no full re-login


def test_discover_market_types_flags_corners_and_cards_candidates():
    fake_client = _FakeClient(_soccer_event_types(), _match_odds_catalogue(), [])
    fake_client.betting._market_types = [
        MarketTypeResult(marketType="MATCH_ODDS", marketCount=1),
        MarketTypeResult(marketType="OVER_UNDER_25", marketCount=1),
        MarketTypeResult(marketType="CORNERS_OVER_UNDER", marketCount=1),
        MarketTypeResult(marketType="TOTAL_BOOKING_POINTS", marketCount=1),
    ]
    provider = BetfairExchangeOddsProvider(
        app_key="k", username="u", password="p", client=fake_client
    )

    discovered = provider.discover_market_types_for_match("Roma", "Inter", KICKOFF_ISO)

    by_code = {d.market_type_code: d for d in discovered}
    assert set(by_code) == {
        "MATCH_ODDS",
        "OVER_UNDER_25",
        "CORNERS_OVER_UNDER",
        "TOTAL_BOOKING_POINTS",
    }
    assert by_code["MATCH_ODDS"].looks_like_corners_or_cards is False
    assert by_code["OVER_UNDER_25"].looks_like_corners_or_cards is False
    assert by_code["CORNERS_OVER_UNDER"].looks_like_corners_or_cards is True
    assert by_code["TOTAL_BOOKING_POINTS"].looks_like_corners_or_cards is True
    # Scoped to the fixture's own real event id, never every football event on Betfair.
    filter_used = fake_client.betting.list_market_types_calls[0]["filter"]
    assert filter_used["eventIds"] == ["30000"]


def test_discover_market_types_returns_empty_when_fixture_not_found():
    fake_client = _FakeClient(
        _soccer_event_types(), _match_odds_catalogue(event_name="Napoli v Juventus"), []
    )
    provider = BetfairExchangeOddsProvider(
        app_key="k", username="u", password="p", client=fake_client
    )

    discovered = provider.discover_market_types_for_match("Roma", "Inter", KICKOFF_ISO)

    assert discovered == []
    assert fake_client.betting.list_market_types_calls == []  # never reached — no event found


def test_ensure_client_falls_back_to_full_relogin_if_keep_alive_fails():
    fake_client = _FakeClient(_soccer_event_types(), [], [])

    def _failing_keep_alive():
        raise RuntimeError("session too stale to renew")

    fake_client.keep_alive = _failing_keep_alive
    provider = BetfairExchangeOddsProvider(
        app_key="k", username="u", password="p", client=fake_client
    )
    provider._ensure_client()
    assert fake_client.login_interactive_calls == 1

    fake_client.session_expired = True
    provider._ensure_client()

    assert fake_client.login_interactive_calls == 2  # fell back to a full re-login
