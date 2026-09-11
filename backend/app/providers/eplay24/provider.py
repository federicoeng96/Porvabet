"""OddsProvider stub for ePlay24 (DATA_SOURCES.md category C — abstract only, NOT implemented).

ePlay24 (E-PLAY24 ITA LTD) is a real, ADM-licensed Italian online bookmaker. Research
for this project found no public API or documented odds feed, and no way to
independently verify its Terms of Service stance on automated access from within
this session's sandboxed network (see DATA_SOURCES.md for exactly what was and
was not verified). Consistent with the project's licensed-bookmaker caution
(same posture as legaseriea.it): this class exists only so the rest of the
codebase can depend on the `OddsProvider` interface, never on ePlay24 directly.

If ePlay24 is ever integrated, it should be through one of:
  - an official partnership/data-licensing agreement, or
  - manual/semi-manual odds entry tooling operated by the user themselves,
never through undocumented scraping of a licensed gambling operator's site.

`is_available()` always returns False; every data method raises NotImplementedError.
"""

from app.models.enums import DataSourceCategory
from app.providers.base.dto import OddsQuoteRecord
from app.providers.base.odds_provider import OddsProvider


class EPlay24OddsProvider(OddsProvider):
    source_key = "eplay24"
    category = DataSourceCategory.C_ABSTRACT_ONLY
    bookmaker_name = "ePlay24"

    def is_available(self) -> bool:
        return False

    def get_odds_for_match(
        self, home_team_name: str, away_team_name: str, kickoff_utc_iso: str
    ) -> list[OddsQuoteRecord]:
        raise NotImplementedError(
            "No verified, automatable access to ePlay24 odds exists — see this "
            "module's docstring and DATA_SOURCES.md. This must never be replaced "
            "with fabricated odds."
        )
