"""SportsDataProvider for SofaScore (DATA_SOURCES.md category B — PERSONAL USE ONLY).

SofaScore's Terms & Conditions (sofascore.com/terms-and-conditions, quoted verbatim
in DATA_SOURCES.md) state the license:

    "does not include any resale or commercial use of the Platform or its contents,
    derivative use, or use of data mining, robots, or similar data gathering tools"

and separately:

    "SofaScore states that they do not supply sports data to bookmakers, and
    bookmakers should not rely on their site to verify bets."

Same posture as WhoScoredProvider (see that module's docstring for the full
rationale): commercial/betting use is explicitly out of scope for SofaScore's own
terms, so this class requires an explicit acknowledgement to instantiate and does
not implement live scraping (endpoints not verified in this session).
"""

from app.models.enums import DataSourceCategory
from app.providers.base.dto import HistoricalMatchRecord
from app.providers.base.sports_data_provider import SportsDataProvider
from app.providers.whoscored.provider import PersonalUseNotAcknowledgedError


class SofaScoreProvider(SportsDataProvider):
    source_key = "sofascore"
    category = DataSourceCategory.B_PERSONAL_USE_ONLY
    # Explicit, code-level (not just a comment) tag for the specific ToS risk —
    # see DATA_SOURCES.md for the verbatim clause and their own FAQ confirming
    # no public API exists at all (not even a paid/commercial one).
    LICENSE_RISK = "personal_use_only_betting_platform_clause"

    def __init__(self, acknowledge_personal_use_only: bool = False) -> None:
        if not acknowledge_personal_use_only:
            raise PersonalUseNotAcknowledgedError(
                "SofaScoreProvider requires acknowledge_personal_use_only=True. "
                "Per SofaScore's ToS, commercial/data-mining use is prohibited and "
                "they explicitly disclaim supplying data to bookmakers — see this "
                "module's docstring and DATA_SOURCES.md before enabling it."
            )
        self._acknowledged = True

    def is_available(self) -> bool:
        return False  # not implemented — see docstring

    def get_historical_matches(
        self, competition_code: str, season_label: str
    ) -> list[HistoricalMatchRecord]:
        raise NotImplementedError(
            "SofaScore scraping is intentionally not implemented in this codebase "
            "(unverified endpoints + ToS risk) — see module docstring."
        )
