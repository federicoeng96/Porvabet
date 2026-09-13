"""Tests for OpenMeteoWeatherProvider — real, documented, key-free REST API
(DATA_SOURCES.md category A). No live network in the test suite: a
`httpx.MockTransport` stands in for the real api.open-meteo.com response,
shaped like the real Open-Meteo hourly-forecast JSON schema."""

import httpx
import pytest

from app.providers.open_meteo.provider import OpenMeteoWeatherProvider

KICKOFF_ISO = "2025-03-01T15:00:00+00:00"


def _mock_client(hourly: dict) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hourly": hourly})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_is_available_is_always_true_no_key_required():
    provider = OpenMeteoWeatherProvider(http_client=_mock_client({}))
    assert provider.is_available() is True


def test_get_forecast_returns_the_matching_hour():
    hourly = {
        "time": ["2025-03-01T14:00", "2025-03-01T15:00", "2025-03-01T16:00"],
        "temperature_2m": [8.0, 9.5, 10.0],
        "precipitation": [0.0, 1.2, 0.0],
        "wind_speed_10m": [10.0, 15.0, 12.0],
        "weathercode": [1, 61, 0],
    }
    provider = OpenMeteoWeatherProvider(http_client=_mock_client(hourly))

    forecast = provider.get_forecast(51.5, -0.1, KICKOFF_ISO)

    assert forecast is not None
    assert forecast.temperature_c == 9.5
    assert forecast.wind_kph == 15.0
    assert forecast.precipitation_mm == 1.2
    assert forecast.condition == "rain"


def test_get_forecast_returns_none_when_hourly_missing():
    provider = OpenMeteoWeatherProvider(http_client=_mock_client({}))

    assert provider.get_forecast(51.5, -0.1, KICKOFF_ISO) is None


def test_get_forecast_returns_none_when_target_hour_not_in_response():
    hourly = {
        "time": ["2025-03-01T20:00"],
        "temperature_2m": [5.0],
        "precipitation": [0.0],
        "wind_speed_10m": [5.0],
        "weathercode": [0],
    }
    provider = OpenMeteoWeatherProvider(http_client=_mock_client(hourly))

    assert provider.get_forecast(51.5, -0.1, KICKOFF_ISO) is None


@pytest.mark.parametrize(
    "code,expected",
    [
        (0, "clear"),
        (2, "cloudy"),
        (45, "fog"),
        (61, "rain"),
        (80, "rain"),
        (71, "snow"),
        (85, "snow"),
        (95, "storm"),
        (99, "storm"),
        (4, "unknown"),
    ],
)
def test_weathercode_mapping(code, expected):
    hourly = {
        "time": ["2025-03-01T15:00"],
        "temperature_2m": [10.0],
        "precipitation": [0.0],
        "wind_speed_10m": [10.0],
        "weathercode": [code],
    }
    provider = OpenMeteoWeatherProvider(http_client=_mock_client(hourly))

    forecast = provider.get_forecast(51.5, -0.1, KICKOFF_ISO)

    assert forecast.condition == expected
