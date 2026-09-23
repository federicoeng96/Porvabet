"""Fallback chain over multiple `OddsProvider`s.

Per the brief: the Value/Odds Engine should be able to use several odds
sources interchangeably through the same `OddsProvider` interface, falling
back automatically if one source is unreachable at a given moment. This
class is that orchestration — it does not know or care which concrete
providers it holds, so it is fully testable with fake providers (see
`tests/test_odds_provider_chain.py`) independently of which real providers
are implemented.

**Recommended priority, updated after The Odds API was added**:
1. `BetfairExchangeOddsProvider` — the official exchange itself, accessed via
   the user's own account (category `D_OFFICIAL_API_PERSONAL_ACCOUNT`, no
   ToS/scraping risk, no request-budget ceiling). Preferred whenever the user
   has configured Betfair credentials and this environment's network can
   reach Betfair (it could not from this sandbox — see DATA_SOURCES.md).
2. `TheOddsApiOddsProvider` — a real, working, commercial aggregator
   (category `E_COMMERCIAL_AGGREGATOR_API`, see DATA_SOURCES.md "Categoria
   E") that relays Betfair Exchange and other bookmakers' prices through its
   own free-tier API (500 credits/month). Kept explicitly AFTER Betfair, not
   before: Betfair's own API has no comparable request ceiling once reachable,
   so trying it first costs nothing extra on a good day and only falls
   through to this scarcer-budget source when Betfair genuinely is not
   configured/reachable — the reverse ordering would burn free-tier credits
   on every single call even when the official source is fine, for no
   benefit.
3. Betson (via diretta.it) and livescore.com remain as documented fallbacks
   after both — still verified-blocked stubs (see DATA_SOURCES.md: Betson by
   this environment's headless-browser limitation, livescore.com by its
   gated affiliate-widget architecture), so today they contribute nothing at
   runtime, but the chain is ready to use either the moment one is
   completed, without any caller change.

This module does not hardcode that composition (callers choose the exact
provider list), but this is the ordering that should be used when wiring
this into the live engine.
"""

import logging

from app.providers.base.dto import OddsQuoteRecord
from app.providers.base.odds_provider import OddsProvider

logger = logging.getLogger(__name__)


def build_default_odds_provider_chain() -> "FallbackOddsProvider":
    """The concrete provider composition this module's docstring recommends:
    Betfair Exchange first (the official source, no request-budget ceiling),
    then The Odds API (a real, working commercial fallback with a scarce
    free-tier budget — see module docstring for why it is not first), then
    the two documented-but-blocked stubs, kept in the chain so it starts
    contributing the moment either is unblocked without any caller change.
    Imported here (rather than at module import time) to avoid a hard
    import-time dependency from this generic orchestrator module onto
    specific concrete provider packages."""
    from app.providers.betfair.provider import BetfairExchangeOddsProvider
    from app.providers.betson_diretta.provider import BetsonDirettaOddsProvider
    from app.providers.livescore.provider import LivescoreOddsProvider
    from app.providers.the_odds_api.provider import TheOddsApiOddsProvider

    return FallbackOddsProvider(
        [
            BetfairExchangeOddsProvider(),
            TheOddsApiOddsProvider(),
            # User-authorized ToS override, already accepted project-wide — see
            # DATA_SOURCES.md and this class' own module docstring. Still
            # `is_available() == False` today (verified technical blocker), so
            # this contributes nothing at runtime, but is kept ready.
            BetsonDirettaOddsProvider(acknowledge_user_override=True),
            LivescoreOddsProvider(),
        ]
    )


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
