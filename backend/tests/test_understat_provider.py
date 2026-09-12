"""Tests for UnderstatProvider — real endpoint/session mechanics (see module
docstring for what was verified live this session), parsing tested here
against a SYNTHETIC fixture matching the real JSON schema (no live network
in the test suite, same convention as test_football_data_provider.py)."""

import json
from datetime import date

import httpx
import pytest

from app.providers.understat.provider import (
    PersonalUseNotAcknowledgedError,
    UnderstatProvider,
)
from tests.fixtures.synthetic_understat_league_data import SYNTHETIC_UNDERSTAT_LEAGUE_DATA


def _mock_client(seen_requests: list) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        if "getLeagueData" in str(request.url):
            return httpx.Response(200, text=json.dumps(SYNTHETIC_UNDERSTAT_LEAGUE_DATA))
        return httpx.Response(200, text="<html>league page</html>")

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_provider_refuses_instantiation_without_acknowledgement():
    with pytest.raises(PersonalUseNotAcknowledgedError):
        UnderstatProvider()


def test_provider_license_risk_flag_is_distinct_from_whoscored_sofascore():
    # Distinct reason from WhoScored/SofaScore's betting-platform ToS clause —
    # understat's risk is a robots.txt disallow-all, not a published ToS clause.
    assert UnderstatProvider.LICENSE_RISK == "personal_use_only_robots_disallow_all"


def test_fetch_visits_league_page_before_the_data_endpoint_for_session_cookie():
    seen: list = []
    provider = UnderstatProvider(http_client=_mock_client(seen), acknowledge_personal_use_only=True)
    provider.get_historical_matches("EPL", "2023/2024")

    assert len(seen) == 2
    assert str(seen[0].url) == "https://understat.com/league/EPL/2023"
    assert "getLeagueData/EPL/2023" in str(seen[1].url)
    assert seen[1].headers["referer"] == "https://understat.com/league/EPL/2023"


def test_get_historical_matches_parses_results_and_skips_unplayed_fixtures():
    provider = UnderstatProvider(
        http_client=_mock_client([]), acknowledge_personal_use_only=True
    )
    records = provider.get_historical_matches("EPL", "2023/2024")

    assert len(records) == 1  # the isResult=False fixture is skipped
    r = records[0]
    assert r.home_team_name == "Synthetic United"
    assert r.away_team_name == "Synthetic City"
    assert r.home_goals_ft == 2
    assert r.away_goals_ft == 1
    assert r.external_ref == "9001"


def test_get_historical_matches_rejects_unknown_competition():
    provider = UnderstatProvider(
        http_client=_mock_client([]), acknowledge_personal_use_only=True
    )
    with pytest.raises(ValueError):
        provider.get_historical_matches("BUNDESLIGA", "2023/2024")


def test_get_team_match_tactical_stats_parses_both_teams():
    provider = UnderstatProvider(
        http_client=_mock_client([]), acknowledge_personal_use_only=True
    )
    stats = provider.get_team_match_tactical_stats("EPL", "2023/2024")

    assert len(stats) == 2
    home = next(s for s in stats if s.team_name == "Synthetic United")
    assert home.is_home is True
    assert home.xg == pytest.approx(1.82)
    assert home.xga == pytest.approx(0.74)
    assert home.ppda_att == 210
    assert home.ppda_def == 18
    assert home.deep == 8
    assert home.match_date == date(2023, 8, 12)

    away = next(s for s in stats if s.team_name == "Synthetic City")
    assert away.is_home is False
    assert away.xg == pytest.approx(0.74)
