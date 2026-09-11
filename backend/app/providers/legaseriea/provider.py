"""SportsDataProvider stub for legaseriea.it (DATA_SOURCES.md category C — NOT implemented).

Lega Serie A's own terms explicitly prohibit "data mining, robot o simili
dispositivi di acquisizione o estrazione" and restrict use to personal,
non-commercial purposes; separately, official match data rights are held under
an exclusive license by Genius Sports through the 2028/29 season, so this data
is not even purchasable as an independent commercial feed. Serie A coverage in
this project is instead sourced from football-data.co.uk / API-Football / etc.
(see DATA_SOURCES.md). This class exists only to keep the interface complete —
`is_available()` always returns False; every data method raises NotImplementedError.
"""

from app.models.enums import DataSourceCategory
from app.providers.base.dto import HistoricalMatchRecord
from app.providers.base.sports_data_provider import SportsDataProvider


class LegaSerieAProvider(SportsDataProvider):
    source_key = "legaseriea"
    category = DataSourceCategory.C_ABSTRACT_ONLY

    def is_available(self) -> bool:
        return False

    def get_historical_matches(
        self, competition_code: str, season_label: str
    ) -> list[HistoricalMatchRecord]:
        raise NotImplementedError(
            "legaseriea.it forbids automated data extraction in its own terms and "
            "its match data rights are exclusively licensed to a third party — see "
            "this module's docstring and DATA_SOURCES.md."
        )
