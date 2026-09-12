"""Tests the OddsProvider fallback-chain orchestration logic in isolation, with
fake providers — this is legitimate even though no real OddsProvider is
implemented yet (Betson/diretta.it and livescore.com are both verified-blocked
stubs, see DATA_SOURCES.md): the chain's job is pure orchestration over
whatever providers it is given, so it must be correct before either real
source exists, and stays correct unchanged once one is completed.
"""

from datetime import UTC, datetime

import pytest

from app.models.enums import DataSourceCategory
from app.providers.base.dto import OddsQuoteRecord
from app.providers.base.odds_provider import OddsProvider
from app.providers.base.odds_provider_chain import FallbackOddsProvider


class _FakeOddsProvider(OddsProvider):
    def __init__(self, source_key, bookmaker_name, available, quotes=None, raises=False):
        self.source_key = source_key
        self.bookmaker_name = bookmaker_name
        self.category = DataSourceCategory.C_ABSTRACT_ONLY
        self._available = available
        self._quotes = quotes or []
        self._raises = raises
        self.calls = 0

    def is_available(self) -> bool:
        return self._available

    def get_odds_for_match(self, home_team_name, away_team_name, kickoff_utc_iso):
        self.calls += 1
        if self._raises:
            raise NotImplementedError("fake provider intentionally not implemented")
        return self._quotes


def _quote(bookmaker: str) -> OddsQuoteRecord:
    return OddsQuoteRecord(
        bookmaker=bookmaker,
        market_label="1X2",
        outcome_code="HOME",
        decimal_odds=2.10,
        captured_at=datetime(2026, 9, 12, tzinfo=UTC),
    )


def test_requires_at_least_one_provider():
    with pytest.raises(ValueError):
        FallbackOddsProvider([])


def test_is_available_if_any_underlying_provider_is_available():
    primary = _FakeOddsProvider("primary", "Primary", available=False)
    backup = _FakeOddsProvider("backup", "Backup", available=True)
    chain = FallbackOddsProvider([primary, backup])
    assert chain.is_available() is True


def test_not_available_when_no_provider_is_available():
    primary = _FakeOddsProvider("primary", "Primary", available=False)
    backup = _FakeOddsProvider("backup", "Backup", available=False)
    chain = FallbackOddsProvider([primary, backup])
    assert chain.is_available() is False


def test_uses_primary_when_available_and_non_empty():
    primary = _FakeOddsProvider("primary", "Primary", available=True, quotes=[_quote("Primary")])
    backup = _FakeOddsProvider("backup", "Backup", available=True, quotes=[_quote("Backup")])
    chain = FallbackOddsProvider([primary, backup])

    result = chain.get_odds_for_match("Home", "Away", "2026-09-12T18:45:00Z")

    assert [q.bookmaker for q in result] == ["Primary"]
    assert primary.calls == 1
    assert backup.calls == 0  # never falls through once the primary succeeds


def test_falls_back_when_primary_unavailable():
    primary = _FakeOddsProvider("primary", "Primary", available=False)
    backup = _FakeOddsProvider("backup", "Backup", available=True, quotes=[_quote("Backup")])
    chain = FallbackOddsProvider([primary, backup])

    result = chain.get_odds_for_match("Home", "Away", "2026-09-12T18:45:00Z")

    assert [q.bookmaker for q in result] == ["Backup"]
    assert primary.calls == 0  # unavailable providers are skipped, never called


def test_falls_back_when_primary_raises_not_implemented():
    primary = _FakeOddsProvider("primary", "Primary", available=True, raises=True)
    backup = _FakeOddsProvider("backup", "Backup", available=True, quotes=[_quote("Backup")])
    chain = FallbackOddsProvider([primary, backup])

    result = chain.get_odds_for_match("Home", "Away", "2026-09-12T18:45:00Z")

    assert [q.bookmaker for q in result] == ["Backup"]


def test_falls_back_when_primary_returns_empty_list():
    primary = _FakeOddsProvider("primary", "Primary", available=True, quotes=[])
    backup = _FakeOddsProvider("backup", "Backup", available=True, quotes=[_quote("Backup")])
    chain = FallbackOddsProvider([primary, backup])

    result = chain.get_odds_for_match("Home", "Away", "2026-09-12T18:45:00Z")

    assert [q.bookmaker for q in result] == ["Backup"]


def test_returns_empty_list_when_all_providers_fail_or_unavailable():
    primary = _FakeOddsProvider("primary", "Primary", available=False)
    backup = _FakeOddsProvider("backup", "Backup", available=True, raises=True)
    chain = FallbackOddsProvider([primary, backup])

    result = chain.get_odds_for_match("Home", "Away", "2026-09-12T18:45:00Z")

    assert result == []
