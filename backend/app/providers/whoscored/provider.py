"""SportsDataProvider for WhoScored (DATA_SOURCES.md category B — PERSONAL USE ONLY).

WhoScored's Terms of Use (whoscored.com/termsofuse, quoted verbatim in
DATA_SOURCES.md) state:

    "The copying, downloading, reproduction, republication, framing, broadcasting
    and transmission of WhoScored.com content including but not limited to all
    statistics, data, products, tables, graphics and other information is
    prohibited without an official licence."

    "The use of WhoScored.com ratings by media, betting or fantasy platforms
    requires an official licence."

That second clause names betting platforms explicitly. This project is a betting
analysis engine, so **any use of this provider beyond the user's own private,
non-redistributed, personal use is a ToS violation**, and the user has accepted
that risk knowingly for their own private use only (see DATA_SOURCES.md). This
class therefore:

  1. refuses to instantiate without an explicit, non-default acknowledgement, and
  2. does not implement live scraping — WhoScored's actual data endpoints were not
     verified in this session, and reverse-engineering them is exactly the kind of
     "invented endpoint" this project's quality bar forbids. Implementing the real
     HTTP calls is left to the user, after they have (a) confirmed they accept the
     ToS risk above and (b) inspected the site's current markup/endpoints themselves.

WhoScored is rich in player ratings and tactical event data that would be valuable
for the Intelligence/Matchup Engine — hence keeping the interface in place — but it
must never be silently wired into ingestion alongside the category-A sources.
"""

from app.models.enums import DataSourceCategory
from app.providers.base.dto import HistoricalMatchRecord
from app.providers.base.sports_data_provider import SportsDataProvider


class PersonalUseNotAcknowledgedError(RuntimeError):
    pass


class WhoScoredProvider(SportsDataProvider):
    source_key = "whoscored"
    category = DataSourceCategory.B_PERSONAL_USE_ONLY
    # Explicit, code-level (not just a comment) tag for the specific ToS clause
    # this provider is at risk under — see DATA_SOURCES.md for the verbatim text
    # and confirmation that it names betting platforms explicitly, not just a
    # generic copy/redistribution restriction.
    LICENSE_RISK = "personal_use_only_betting_platform_clause"

    def __init__(self, acknowledge_personal_use_only: bool = False) -> None:
        if not acknowledge_personal_use_only:
            raise PersonalUseNotAcknowledgedError(
                "WhoScoredProvider requires acknowledge_personal_use_only=True. "
                "Per WhoScored's ToS, betting-platform use requires an official "
                "licence this project does not have — see this module's docstring "
                "and DATA_SOURCES.md before enabling it."
            )
        self._acknowledged = True

    def is_available(self) -> bool:
        return False  # not implemented — see docstring

    def get_historical_matches(
        self, competition_code: str, season_label: str
    ) -> list[HistoricalMatchRecord]:
        raise NotImplementedError(
            "WhoScored scraping is intentionally not implemented in this codebase "
            "(unverified endpoints + ToS risk) — see module docstring."
        )
