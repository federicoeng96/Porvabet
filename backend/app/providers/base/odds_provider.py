from abc import ABC, abstractmethod

from app.models.enums import DataSourceCategory
from app.providers.base.dto import OddsQuoteRecord


class OddsProvider(ABC):
    """A source of bookmaker odds for a match, live or historical closing lines.

    See DATA_SOURCES.md for the concrete assessment of ePlay24: as of this writing
    there is no known automatable public access, so `EPlay24OddsProvider` exists only
    as a documented, non-functional stub (category C) — the application code depends
    only on this interface, never on ePlay24 directly, so a future real integration
    (an official feed, a licensed data partner, or manual entry tooling) can be added
    without touching the decision layer.
    """

    source_key: str
    category: DataSourceCategory
    bookmaker_name: str

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def get_odds_for_match(
        self, home_team_name: str, away_team_name: str, kickoff_utc_iso: str
    ) -> list[OddsQuoteRecord]:
        """Return current odds quotes for a match. Must return an empty list — never
        synthetic numbers — when odds cannot actually be retrieved."""
