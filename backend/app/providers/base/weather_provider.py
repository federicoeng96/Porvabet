from abc import ABC, abstractmethod

from app.models.enums import DataSourceCategory
from app.providers.base.dto import WeatherForecastRecord


class WeatherProvider(ABC):
    """A source of match-day weather forecasts.

    Used only as a feature input where plausible and measurable (e.g. wind/rain
    affecting total-goals or corners markets) — never applied as a blanket
    adjustment to every market (see prompt: "solo quando ... impatto plausibile").
    """

    source_key: str
    category: DataSourceCategory

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def get_forecast(
        self, latitude: float, longitude: float, kickoff_utc_iso: str
    ) -> WeatherForecastRecord | None: ...
