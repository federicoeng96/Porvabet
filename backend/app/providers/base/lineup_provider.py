from abc import ABC, abstractmethod

from app.models.enums import DataSourceCategory
from app.providers.base.dto import LineupProjectionRecord


class LineupProvider(ABC):
    """A source of official or probable lineups.

    Per the spec: probable-lineup sources (SOS Fanta, Gazzetta dello Sport) are
    reconciled by the ingestion/decision layer, not inside a single provider —
    when two LineupProvider results disagree for the same match, the decision
    layer lowers confidence and blocks player markets from becoming the main
    selection (see MODEL_SPEC.md "Lineup conflict handling").
    """

    source_key: str
    category: DataSourceCategory
    is_official_source: bool  # True only for the competition's own official lineup feed

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def get_probable_lineups(
        self, home_team_name: str, away_team_name: str, kickoff_utc_iso: str
    ) -> list[LineupProjectionRecord]:
        """Return 0, 1 or 2 LineupProjectionRecord (home/away) for the match."""
