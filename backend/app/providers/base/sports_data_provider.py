from abc import ABC, abstractmethod

from app.models.enums import DataSourceCategory
from app.providers.base.dto import HistoricalMatchRecord, UpcomingFixtureRecord


class SportsDataProvider(ABC):
    """A source of historical results, fixtures and match/team/player statistics.

    Implementations must never fabricate a value: if a field cannot be sourced,
    it must be omitted (None / empty collection), not estimated or guessed inside
    the provider. Estimation belongs to the statistical engine, which can reason
    about missing data explicitly (see MODEL_SPEC.md).
    """

    source_key: str
    category: DataSourceCategory

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this provider is currently usable (e.g. credentials configured,
        network reachable). Ingestion must skip an unavailable provider rather than
        substituting fabricated data."""

    @abstractmethod
    def get_historical_matches(
        self, competition_code: str, season_label: str
    ) -> list[HistoricalMatchRecord]:
        """Return completed matches for one competition/season."""

    def get_upcoming_fixtures(
        self, competition_code: str, season_label: str
    ) -> list[UpcomingFixtureRecord]:
        """Return scheduled matches. Optional: not every source lists fixtures."""
        raise NotImplementedError(f"{self.source_key} does not implement fixture listing")
