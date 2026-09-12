"""Tests BetfairExchangeOddsProvider's request-building/response-parsing logic
against a fake client built from betfairlightweight's own real resource
classes (EventTypeResult, MarketCatalogue, MarketBook, etc., constructed with
the same camelCase field names Betfair's real JSON-RPC responses use) — never
against the live Betfair API, since no account/credentials were available in
this session (see the provider module's docstring and DATA_SOURCES.md).
"""

import pytest
from betfairlightweight.resources.bettingresources import (
    EventTypeResult,
    MarketBook,
    MarketCatalogue,
)

from app.models.enums import DataSourceCategory
from app.providers.betfair.provider import (
    BETFAIR_BOOKMAKER_LABEL,
    BetfairCredentialsMissingError,
    BetfairExchangeOddsProvider,
)

KICKOFF_ISO = "2026-09-12T18:45:00Z"


class _FakeBetting:
    def __init__(self, event_types, catalogues, books):
        self._event_types = event_types
        self._catalogues = catalogues
        self._books = books
        self.list_market_catalogue_calls = []
        self.list_market_book_calls = []

    def list_event_types(self, **kwargs):
        return self._event_types

    def list_market_catalogue(self, **kwargs):
        self.list_market_catalogue_calls.append(kwargs)
        return self._catalogues

    def list_market_book(self, **kwargs):
        self.list_market_book_calls.append(kwargs)
        return self._books


class _FakeClient:
    def __init__(self, event_types, catalogues, books):
        self.betting = _FakeBetting(event_types, catalogues, books)
        self.login_calls = 0

    def login(self):
        self.login_calls += 1


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


def test_is_available_requires_all_three_credentials():
    assert BetfairExchangeOddsProvider(app_key=None, username="u", password="p").is_available() is False
    assert BetfairExchangeOddsProvider(app_key="k", username=None, password="p").is_available() is False
    assert BetfairExchangeOddsProvider(app_key="k", username="u", password=None).is_available() is False
    assert BetfairExchangeOddsProvider(app_key="k", username="u", password="p").is_available() is True


def test_raises_clear_error_without_credentials():
    provider = BetfairExchangeOddsProvider(app_key=None, username=None, password=None)
    with pytest.raises(BetfairCredentialsMissingError):
        provider.get_odds_for_match("Roma", "Inter", KICKOFF_ISO)


def test_error_message_names_exact_env_vars_and_key_tier():
    # The user must be able to fix this from the message alone, without
    # reading the source — not a cryptic/generic "missing config" error.
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

    assert fake_client.login_calls == 1  # never re-logged-in once cached
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

    assert fake_client.login_calls == 1
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
