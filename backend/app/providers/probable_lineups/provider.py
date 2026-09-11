"""LineupProvider stubs for SOS Fanta and Gazzetta dello Sport (probable lineups).

Per the spec, Serie A probable-lineup reconciliation relies on these two sources:
when they agree, confidence is high; when they disagree, the conflict must be
surfaced and player-market selections must not become the main pick (see
`app.engine.decision.lineup_reconciliation`).

Neither source's terms of service nor concrete page/endpoint structure was
verified in this project's DATA_SOURCES.md research pass (out of scope of the
sources explicitly listed in the brief) — implementing a real scraper against
either site without that verification would risk exactly the "invented endpoint"
failure mode this project must avoid. These classes therefore document the
intended interface and reconciliation contract, and raise NotImplementedError for
the actual fetch — a real implementation should only be added after (a) directly
inspecting each site's current markup and (b) confirming its terms of use permit
this kind of automated reading, and that should be recorded in DATA_SOURCES.md
before this class is wired into ingestion.
"""

from app.models.enums import DataSourceCategory
from app.providers.base.dto import LineupProjectionRecord
from app.providers.base.lineup_provider import LineupProvider


class SosFantaLineupProvider(LineupProvider):
    source_key = "sos_fanta"
    category = DataSourceCategory.C_ABSTRACT_ONLY
    is_official_source = False

    def is_available(self) -> bool:
        return False

    def get_probable_lineups(
        self, home_team_name: str, away_team_name: str, kickoff_utc_iso: str
    ) -> list[LineupProjectionRecord]:
        raise NotImplementedError(
            "SOS Fanta scraping not implemented — endpoint/ToS not verified. "
            "See module docstring."
        )


class GazzettaLineupProvider(LineupProvider):
    source_key = "gazzetta_dello_sport"
    category = DataSourceCategory.C_ABSTRACT_ONLY
    is_official_source = False

    def is_available(self) -> bool:
        return False

    def get_probable_lineups(
        self, home_team_name: str, away_team_name: str, kickoff_utc_iso: str
    ) -> list[LineupProjectionRecord]:
        raise NotImplementedError(
            "Gazzetta dello Sport scraping not implemented — endpoint/ToS not "
            "verified. See module docstring."
        )
