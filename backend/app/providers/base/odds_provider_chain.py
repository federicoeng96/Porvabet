"""Fallback chain over multiple `OddsProvider`s.

Per the brief: the Value/Odds Engine should be able to use several odds
sources interchangeably through the same `OddsProvider` interface, falling
back automatically if one source is unreachable at a given moment. This
class is that orchestration — it does not know or care which concrete
providers it holds, so it is fully testable with fake providers (see
`tests/test_odds_provider_chain.py`) independently of which real providers
are implemented.

**Recommended priority, updated after Betfair Exchange was added**:
`BetfairExchangeOddsProvider` first — it is the only source in this chain
that is a real, working, officially-sanctioned API (category
`D_OFFICIAL_API_PERSONAL_ACCOUNT`, no ToS/scraping risk at all), so it should
be preferred whenever the user has configured Betfair credentials. Betson
(via diretta.it) and livescore.com remain as documented fallbacks after it —
both are still verified-blocked stubs (see DATA_SOURCES.md: Betson by this
environment's headless-browser limitation, livescore.com by its gated
affiliate-widget architecture), so today they contribute nothing at runtime,
but the chain is ready to use either the moment one is completed, without
any caller change. This module does not hardcode that composition (callers
choose the exact provider list), but this is the ordering that should be
used when wiring this into the live engine.
"""

import logging

from app.providers.base.dto import OddsQuoteRecord
from app.providers.base.odds_provider import OddsProvider

logger = logging.getLogger(__name__)


class FallbackOddsProvider(OddsProvider):
    """Tries each provider in `providers` order; returns the first non-empty
    result. A provider that reports `is_available() is False`, or that raises
    while fetching, is skipped rather than propagating the failure — the whole
    point of a fallback chain is that one source being down does not take the
    others down with it. Any exception from a provider is logged (so a
    genuine bug is still visible) and treated as "this source is down right
    now", not as a fatal error for the whole chain.
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
            except Exception:
                logger.exception(
                    "OddsProvider %s failed fetching %s vs %s — falling back to the next source",
                    provider.source_key,
                    home_team_name,
                    away_team_name,
                )
                continue
            if quotes:
                return quotes
        return []
