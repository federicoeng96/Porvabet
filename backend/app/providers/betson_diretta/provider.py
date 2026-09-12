"""OddsProvider stub for Betson (odds shown via diretta.it/Flashscore).

**This is an explicit, user-authorized ToS override, not an ambiguity-driven
personal-use reading like WhoScored/SofaScore's `B_PERSONAL_USE_ONLY`.**

diretta.it/Flashscore's own terms (flashscore.com/terms-of-use/, quoted verbatim
in DATA_SOURCES.md) prohibit data extraction and scraping outright, with no
personal-use carve-out at all — a flatter, more absolute prohibition than any
other B-category source in this project. The user was shown that clause, is
fully informed there is no personal-use exception, and has explicitly instructed
that this project proceed anyway: they only need indicative pre-match odds for
personal use, never in-play/live odds, and accept the risk to their own access
to the site consciously. See DATA_SOURCES.md for the dated override statement.

`LICENSE_RISK` is deliberately a different string than any `B_PERSONAL_USE_ONLY`
provider uses, specifically to make this distinction visible in code, not just
in prose: this is a *known, explicit, absolute prohibition being knowingly
overridden*, never an ambiguous clause being interpreted in the user's favor.

**Why this is still not implemented (verified technical blocker, not a policy
choice):** the pre-match odds shown on diretta.it are not present in the
server-rendered HTML of a match page — they load only after the page's client
JS runs (confirmed by fetching a real Serie A match page directly: the "Quote
pre-partita" tab content is empty in the raw HTML). Reproducing that would
require either (a) a real browser actually executing the page, or (b) calling
diretta.it/Flashscore's underlying feed API directly. (b) was explicitly not
attempted beyond reading literal config already present in the page: the feed
base URL (`https://400.flashscore.ninja`) is visible in the page's own inline
config, but its request-signing scheme is not documented anywhere reachable in
this session, and guessing a path/signature would be exactly the "invented
endpoint" this project's quality bar forbids. (a) was attempted with Playwright
against the real Chromium binary available in this environment, and failed for
an environment reason, not a diretta.it block: this sandboxed session's network
proxy resets the TLS handshake for *any* external HTTPS host reached through a
full browser engine (verified against google.com and accounts.google.com too,
not just diretta.it — same failure signature every time). See DATA_SOURCES.md
for the full technical trace.

So: the ToS override is real and user-authorized, the odds genuinely exist and
were seen referenced live on the site (UI strings "Quote pre-partita" /
"Quote scommesse sportive" confirmed via a real request), but no working code
path to actually fetch them exists in this session. `is_available()` therefore
still returns False and the fetch method still raises — this is an honest
"verified blocked", the same treatment already given to fbref (Cloudflare) and
ePlay24 (Akamai) in this project, not a silent skip.

Whoever completes this later (in an environment where a headless browser can
actually reach the internet) must:
  - use a real browser (Playwright/Chromium), not a guessed feed URL/signature;
  - read only the "Quote pre-partita" (pre-match) tab, never live/in-play odds,
    even though the same page technically also serves those;
  - label every quote, in code/logs/UI, as "Betson (via diretta.it)" — never
    generically "bookmaker" — since the odds are diretta.it's display of a
    third-party bookmaker's price, not diretta.it's own data (see DATA_SOURCES.md
    point 3 on the Betson/diretta.it licensing chain);
  - rate-limit conservatively (see `app.core.rate_limiter.RateLimiter`, already
    used by `FbrefProvider`) to reduce the chance of the user's IP being blocked.
"""

from app.models.enums import DataSourceCategory
from app.providers.base.dto import OddsQuoteRecord
from app.providers.base.odds_provider import OddsProvider

BETSON_DIRETTA_BOOKMAKER_LABEL = "Betson (via diretta.it)"


class BetsonTosOverrideNotAcknowledgedError(RuntimeError):
    pass


class BetsonDirettaOddsProvider(OddsProvider):
    source_key = "betson_diretta"
    category = DataSourceCategory.C_ABSTRACT_ONLY
    bookmaker_name = BETSON_DIRETTA_BOOKMAKER_LABEL

    # Distinct, code-visible marker for an *explicit prohibition knowingly
    # overridden by the user*, as opposed to B_PERSONAL_USE_ONLY's "ambiguous
    # clause interpreted narrowly" risk. See module docstring and
    # DATA_SOURCES.md for the verbatim ToS clause this overrides.
    LICENSE_RISK = "explicit_tos_prohibition_no_personal_use_exception_user_override"

    def __init__(self, acknowledge_user_override: bool = False) -> None:
        if not acknowledge_user_override:
            raise BetsonTosOverrideNotAcknowledgedError(
                "BetsonDirettaOddsProvider requires acknowledge_user_override=True. "
                "diretta.it/Flashscore's ToS prohibit scraping/extraction outright, "
                "with no personal-use exception. The user has explicitly chosen to "
                "override this, for pre-match odds only, at their own risk — see "
                "this module's docstring and DATA_SOURCES.md before enabling it."
            )
        self._acknowledged = True

    def is_available(self) -> bool:
        return False  # verified technical blocker — see module docstring

    def get_odds_for_match(
        self, home_team_name: str, away_team_name: str, kickoff_utc_iso: str
    ) -> list[OddsQuoteRecord]:
        raise NotImplementedError(
            "Betson (via diretta.it) pre-match odds fetching is not implemented: "
            "the odds are only present after client-side JS renders the page, and "
            "this session's sandboxed network cannot get a real browser engine to "
            "any external host (verified, not diretta.it-specific — see this "
            "module's docstring and DATA_SOURCES.md). Never replace this with "
            "fabricated or guessed-endpoint odds."
        )
