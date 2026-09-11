"""Real WeatherProvider using Open-Meteo (open-meteo.com), DATA_SOURCES.md category A.

Open-Meteo is a free, no-API-key weather forecast API intended for non-commercial
use without attribution requirements beyond a link back (commercial use requires a
paid plan — this project's usage here is a personal/research analytical tool, not
resale of weather data, but re-check open-meteo.com/en/license if usage patterns
change). This is a genuinely public, stable, documented REST API (not scraping),
so unlike the sports-specific sources it does not need the same ToS caution.
"""

from datetime import UTC, datetime

import httpx

from app.models.enums import DataSourceCategory
from app.providers.base.dto import WeatherForecastRecord
from app.providers.base.weather_provider import WeatherProvider

BASE_URL = "https://api.open-meteo.com/v1/forecast"


class OpenMeteoWeatherProvider(WeatherProvider):
    source_key = "open_meteo"
    category = DataSourceCategory.A_UNRESTRICTED

    def __init__(self, http_client: httpx.Client | None = None, timeout_s: float = 15.0) -> None:
        self._client = http_client or httpx.Client(timeout=timeout_s)

    def is_available(self) -> bool:
        return True

    def get_forecast(
        self, latitude: float, longitude: float, kickoff_utc_iso: str
    ) -> WeatherForecastRecord | None:
        kickoff = datetime.fromisoformat(kickoff_utc_iso).astimezone(UTC)
        response = self._client.get(
            BASE_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "hourly": "temperature_2m,precipitation,wind_speed_10m,weathercode",
                "timezone": "UTC",
                "start_date": kickoff.date().isoformat(),
                "end_date": kickoff.date().isoformat(),
            },
        )
        response.raise_for_status()
        payload = response.json()
        hourly = payload.get("hourly")
        if not hourly:
            return None

        target_hour_iso = kickoff.strftime("%Y-%m-%dT%H:00")
        try:
            idx = hourly["time"].index(target_hour_iso)
        except ValueError:
            return None

        return WeatherForecastRecord(
            kickoff_utc=kickoff,
            temperature_c=hourly["temperature_2m"][idx],
            wind_kph=hourly["wind_speed_10m"][idx],
            precipitation_mm=hourly["precipitation"][idx],
            condition=_weathercode_to_condition(hourly["weathercode"][idx]),
            forecast_at=datetime.now(UTC).date(),
        )


def _weathercode_to_condition(code: int) -> str:
    # WMO weather interpretation codes, per Open-Meteo docs.
    if code == 0:
        return "clear"
    if code in (1, 2, 3):
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    if 71 <= code <= 77 or 85 <= code <= 86:
        return "snow"
    if code >= 95:
        return "storm"
    return "unknown"
