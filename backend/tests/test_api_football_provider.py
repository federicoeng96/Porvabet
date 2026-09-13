"""Tests for ApiFootballProvider — API-Football v3 REST shape, against a
SYNTHETIC response matching the real documented schema (no live network in
the test suite, no real API key needed)."""

from datetime import UTC, datetime

import httpx
import pytest

from app.config import settings
from app.providers.api_football import provider as api_football_module
from app.providers.api_football.provider import ApiFootballProvider

SYNTHETIC_FIXTURES_RESPONSE = {
    "response": [
        {
            "fixture": {
                "id": 12345,
                "date": "2025-03-01T15:00:00+00:00",
                "referee": "Synthetic Referee",
            },
            "teams": {
                "home": {"name": "Synthetic United"},
                "away": {"name": "Synthetic City"},
            },
            "goals": {"home": 2, "away": 1},
            "score": {"halftime": {"home": 1, "away": 0}},
        }
    ]
}


def _mock_client(payload: dict) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.Client(base_url=api_football_module.BASE_URL, transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _clear_api_football_key(monkeypatch):
    monkeypatch.setattr(settings, "api_football_key", None)


def test_is_available_false_without_a_key():
    provider = ApiFootballProvider(http_client=_mock_client({}))
    assert provider.is_available() is False


def test_is_available_true_with_a_key(monkeypatch):
    monkeypatch.setattr(settings, "api_football_key", "synthetic-key")
    provider = ApiFootballProvider(http_client=_mock_client({}))
    assert provider.is_available() is True


def test_get_historical_matches_refuses_without_a_key():
    provider = ApiFootballProvider(http_client=_mock_client({}))
    with pytest.raises(RuntimeError):
        provider.get_historical_matches("EPL", "2024/2025")


def test_get_upcoming_fixtures_refuses_without_a_key():
    provider = ApiFootballProvider(http_client=_mock_client({}))
    with pytest.raises(RuntimeError):
        provider.get_upcoming_fixtures("EPL", "2024/2025")


def test_get_historical_matches_parses_the_real_response_shape(monkeypatch):
    monkeypatch.setattr(settings, "api_football_key", "synthetic-key")
    provider = ApiFootballProvider(http_client=_mock_client(SYNTHETIC_FIXTURES_RESPONSE))

    records = provider.get_historical_matches("EPL", "2024/2025")

    assert len(records) == 1
    r = records[0]
    assert r.home_team_name == "Synthetic United"
    assert r.away_team_name == "Synthetic City"
    assert r.home_goals_ft == 2
    assert r.away_goals_ft == 1
    assert r.home_goals_ht == 1
    assert r.away_goals_ht == 0
    assert r.referee_name == "Synthetic Referee"
    assert r.external_ref == "12345"
    assert r.kickoff_utc == datetime(2025, 3, 1, 15, 0, tzinfo=UTC)


def test_get_upcoming_fixtures_parses_the_real_response_shape(monkeypatch):
    monkeypatch.setattr(settings, "api_football_key", "synthetic-key")
    upcoming_payload = {
        "response": [
            {
                "fixture": {"id": 999, "date": "2025-04-01T12:30:00+00:00"},
                "teams": {
                    "home": {"name": "Synthetic Rovers"},
                    "away": {"name": "Synthetic Athletic"},
                },
            }
        ]
    }
    provider = ApiFootballProvider(http_client=_mock_client(upcoming_payload))

    records = provider.get_upcoming_fixtures("EPL", "2024/2025")

    assert len(records) == 1
    r = records[0]
    assert r.home_team_name == "Synthetic Rovers"
    assert r.away_team_name == "Synthetic Athletic"
    assert r.external_ref == "999"
    assert r.competition_code == "EPL"
