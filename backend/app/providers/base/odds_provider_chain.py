"""Fallback chain over multiple `OddsProvider`s.

Per the brief: the Value/Odds Engine should be able to use Betson (via
diretta.it) or livescore.com interchangeably through the same `OddsProvider`
interface, falling back automatically if one source is unreachable at a given
moment. This class is that orchestration — it does not know or care which
concrete providers it holds, so it is fully testable with fake providers (see
`tests/providers/test_odds_provider_chain.py`) independently of whether any
real provider is implemented yet.

**Default priority, as instructed**: Betson (via diretta.it) first, livescore.com
second. Betson/diretta.it is the user's explicitly named primary source;
livescore.com is the explicitly named backup. Neither is actually implemented
yet (both raise `NotImplementedError` — see their modules and DATA_SOURCES.md),
so today this chain has nothing real to fall back between; it exists so that
whichever one is completed first (or both) slots in without changing any
caller.
"""

from app.providers.base.dto import OddsQuoteRecord
from app.providers.base.odds_provider import OddsProvider


class FallbackOddsProvider(OddsProvider):
    """Tries each provider in `providers` order; returns the first non-empty
    result. A provider that reports `is_available() is False`, or that raises
    while fetching, is skipped rather than propagating the failure — the whole
    point of a fallback chain is that one source being down does not take the
    others down with it.
    """

    source_key = "odds_fallback_chain"

    def __init__(self, providers: list[OddsProvider]) -> None:
        if not providers:
            raise ValueError("FallbackOddsProvider requires at least one provider")
        self._providers = providers
        # No single fixed category/bookmaker_name — these vary per underlying
        # provider actually used for a given call. Callers needing to label a
        # specific quote should use the label on the OddsQuoteRecord's source,
        # not on this chain object.
        self.category = providers[0].category
        self.bookmaker_name = "/".join(p.bookmaker_name for p in providers)

    def is_available(self) -> bool:
        return any(p.is_available() for p in self._providers)

    def get_odds_for_match(
        self, home_team_name: str, away_team_name: str, kickoff_utc_iso: str
    ) -> list[OddsQuoteRecord]:
        for provider in self._providers:
            if not provider.is_available():
                continue
            try:
                quotes = provider.get_odds_for_match(
                    home_team_name, away_team_name, kickoff_utc_iso
                )
            except NotImplementedError:
                continue
            if quotes:
                return quotes
        return []
