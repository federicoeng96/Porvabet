"""Tests FootballDataOrgFixtureProvider's request-building/response-parsing
logic against an `httpx.MockTransport` built from the REAL v4 JSON shapes
verified live this session (see the provider module's docstring for exactly
which URLs were fetched and what they returned) — never against the live
football-data.org API, since no API key was available in this session.
"""

import httpx
import pytest

from app.models.enums import DataSourceCategory
from app.providers.football_data_org.provider import (
    FootballDataOrgApiKeyMissingError,
    FootballDataOrgFixtureProvider,
    FootballDataOrgInvalidApiKeyError,
)

# Real response shape for GET /v4/competitions/PL, copied (fields relevant to
# this provider) from a live curl example on football-data.org's own current
# API docs (https://www.football-data.org/documentation/quickstart).
COMPETITION_RESPONSE = {
    "id": 2021,
    "name": "Premier League",
    "code": "PL",
    "currentSeason": {
        "id": 733,
        "startDate": "2026-08-08",
        "endDate": "2027-05-24",
        "currentMatchday": 5,
    },
}

# Real response shape for GET /v4/competitions/PL/matches?matchday=N, same
# source as above.
MATCHES_RESPONSE = {
    "filters": {"season": "2026", "matchday": "5"},
    "resultSet": {"count": 2, "played": 0},
    "competition": {"id": 2021, "name": "Premier League", "code": "PL"},
    "matches": [
        {
            "id": 500001,
            "utcDate": "2026-09-20T14:00:00Z",
            "status": "TIMED",
            "matchday": 5,
            "season": {"startDate": "2026-08-08", "endDate": "2027-05-24"},
            "homeTeam": {"id": 57, "name": "Arsenal FC"},
            "awayTeam": {"id": 61, "name": "Chelsea FC"},
        },
        {
            "id": 500002,
            "utcDate": "2026-09-20T16:30:00Z",
            "status": "SCHEDULED",
            "matchday": 5,
            "season": {"startDate": "2026-08-08", "endDate": "2027-05-24"},
            "homeTeam": {"id": 65, "name": "Manchester City FC"},
            "awayTeam": {"id": 66, "name": "Manchester United FC"},
        },
        {
            # Already played earlier in the same matchday (e.g. moved for TV) —
            # must NOT be returned as an upcoming fixture.
            "id": 500003,
            "utcDate": "2026-09-19T19:00:00Z",
            "status": "FINISHED",
            "matchday": 5,
            "season": {"startDate": "2026-08-08", "endDate": "2027-05-24"},
            "homeTeam": {"id": 73, "name": "Tottenham Hotspur FC"},
            "awayTeam": {"id": 76, "name": "Wolverhampton Wanderers FC"},
        },
    ],
}


def _fake_client(expected_key: str = "real-test-key") -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("X-Auth-Token") != expected_key:
            return httpx.Response(400, json={"message": "Your API token is invalid."})
        if request.url.path == "/v4/competitions/PL" and "matches" not in request.url.path:
            return httpx.Response(200, json=COMPETITION_RESPONSE)
        if request.url.path == "/v4/competitions/PL/matches":
            assert request.url.params["matchday"] == "5"
            return httpx.Response(200, json=MATCHES_RESPONSE)
        return httpx.Response(404, json={"message": "not found in this fake"})

    return httpx.Client(base_url="https://api.football-data.org/v4", transport=httpx.MockTransport(handler))


def test_category_is_unrestricted():
    provider = FootballDataOrgFixtureProvider(api_key="k", http_client=_fake_client())
    assert provider.category == DataSourceCategory.A_UNRESTRICTED


def test_is_available_requires_api_key(monkeypatch):
    monkeypatch.setattr(
        "app.providers.football_data_org.provider.settings.football_data_org_api_key", None
    )
    assert FootballDataOrgFixtureProvider(api_key=None).is_available() is False
    assert FootballDataOrgFixtureProvider(api_key="k").is_available() is True


def test_raises_clear_error_without_api_key(monkeypatch):
    monkeypatch.setattr(
        "app.providers.football_data_org.provider.settings.football_data_org_api_key", None
    )
    provider = FootballDataOrgFixtureProvider(api_key=None)
    with pytest.raises(FootballDataOrgApiKeyMissingError) as exc_info:
        provider.get_next_matchday_fixtures("EPL")
    assert "FOOTBALL_DATA_ORG_API_KEY" in str(exc_info.value)


def test_get_current_matchday_reads_real_field_path():
    provider = FootballDataOrgFixtureProvider(api_key="real-test-key", http_client=_fake_client())
    assert provider.get_current_matchday("EPL") == 5


def test_get_next_matchday_fixtures_excludes_finished_matches():
    provider = FootballDataOrgFixtureProvider(api_key="real-test-key", http_client=_fake_client())

    records = provider.get_next_matchday_fixtures("EPL")

    assert len(records) == 2  # the FINISHED one is excluded
    by_home = {r.home_team_name: r for r in records}
    assert set(by_home) == {"Arsenal FC", "Manchester City FC"}

    arsenal_fixture = by_home["Arsenal FC"]
    assert arsenal_fixture.away_team_name == "Chelsea FC"
    assert arsenal_fixture.competition_code == "EPL"
    assert arsenal_fixture.season_label == "2026/2027"
    assert arsenal_fixture.external_ref == "football_data_org:500001"
    assert arsenal_fixture.kickoff_utc.isoformat() == "2026-09-20T14:00:00+00:00"


def test_wrong_api_key_raises_clear_error_not_silent_empty_list():
    # A configured-but-wrong key must never be treated as "no key" (which
    # degrades silently via is_available()=False) nor surface a bare
    # httpx.HTTPStatusError — the user needs a message naming the env var
    # and pointing at the real API's own rejection reason, not a traceback.
    provider = FootballDataOrgFixtureProvider(api_key="wrong-key", http_client=_fake_client())
    with pytest.raises(FootballDataOrgInvalidApiKeyError) as exc_info:
        provider.get_next_matchday_fixtures("EPL")
    message = str(exc_info.value)
    assert "FOOTBALL_DATA_ORG_API_KEY" in message
    assert "Your API token is invalid" in message  # the real API's own wording, not paraphrased


def test_wrong_api_key_error_also_raised_from_get_current_matchday():
    provider = FootballDataOrgFixtureProvider(api_key="wrong-key", http_client=_fake_client())
    with pytest.raises(FootballDataOrgInvalidApiKeyError):
        provider.get_current_matchday("EPL")


def test_unrelated_http_error_still_surfaces_normally():
    # A 404 (or any non-auth-shaped error) must NOT be swallowed/reworded —
    # only the two specific auth failure modes verified live get a custom
    # message; everything else stays a plain httpx.HTTPStatusError.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "not found"})

    client = httpx.Client(
        base_url="https://api.football-data.org/v4", transport=httpx.MockTransport(handler)
    )
    provider = FootballDataOrgFixtureProvider(api_key="real-test-key", http_client=client)
    with pytest.raises(httpx.HTTPStatusError):
        provider.get_current_matchday("EPL")
