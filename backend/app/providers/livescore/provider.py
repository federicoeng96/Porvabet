"""OddsProvider stub for livescore.com — backup source for the Betson/diretta.it
pre-match odds provider (DATA_SOURCES.md category C — abstract only, NOT
implemented).

**Audited independently from diretta.it/Flashscore, per explicit instruction not
to assume equivalence.** livescore.com is operated by LiveScore Limited (footer
copyright "© 1998-2026 LiveScore Limited", verified live) — a genuinely
different corporate group from Livesport a.s./Flashscore (diretta.it), not just
a differently-branded mirror. Its own bookmaker brand, "LiveScoreBet"
(livescorebet.com), also appears directly in the app's own config, which
diretta.it/Flashscore has no equivalent of.

**Why this is not implemented, and why the reason is different from
diretta.it's:**

1. **The odds feature is not a plain data table.** livescore.com's match pages
   are server-rendered Next.js pages (verified live: the page embeds a real
   `__NEXT_DATA__` JSON blob server-side, unlike diretta.it which renders
   nothing match-specific without client JS) — but the "Odds" tab's actual
   bookmaker prices are not in that JSON. They come from separate,
   country/user-attribute-gated `e2Widgets` config entries
   (`odds-comparison`, `smart-odds`, `odds-boost`) whose `user` gate list
   includes `isAdult`, `notSelfExcluded`, `hasBetFeatures` — i.e. livescore.com
   itself treats this as regulated-gambling functionality behind a consent/
   compliance gate, not a public data feed. `odds-comparison` was confirmed
   enabled for `"IT"` in the live config, but the actual bookmaker
   names/prices were never retrieved in this session — the specific match
   checked (`Atalanta vs Cagliari`, today's Serie A fixture, id `1785358`)
   had its own `Odds` tab marked `"isVisible": false` server-side.
2. **No bookmaker names (e.g. "bet365") were ever observed.** The only
   concretely identified in-app betting brand is livescore.com's own
   in-house bookmaker, LiveScoreBet — meaning what little was observable
   looks more like an affiliate/deep-link product than a neutral
   odds-comparison table, though this was not confirmed either way for
   lack of a rendered example.
3. **The full verbatim Terms of Use text could not be retrieved.**
   `/en/terms/` (and its localized variants) serve only a short pre-hydration
   summary ("has terms of use covering areas such as the use of LiveScore
   material...") with no scraping/automation clause visible in it; the actual
   body text loads client-side after JS hydration, which — same as for
   diretta.it — could not be exercised in this session (see below).
4. **Headless-browser access is blocked in this session for infrastructure
   reasons, not a livescore.com-specific block** — see
   `app.providers.betson_diretta.provider` docstring and DATA_SOURCES.md for
   the verified trace (this session's proxy resets the TLS handshake for any
   external host reached through a real browser engine, confirmed against
   unrelated hosts too).

`robots.txt` (`https://www.livescore.com/robots.txt` and the "legacy" mirror
`https://www.livescores.com/robots.txt`, both verified live) allow `/` generally
for an unnamed user-agent but explicitly disallow `/api/`, and the legacy
mirror additionally disallows several AI-crawler user agents by name (including
`ClaudeBot`). Neither disallows ordinary page paths for a generic browser
user-agent, so — unlike diretta.it's absolute anti-scraping ToS clause —
nothing found here amounts to as unambiguous a prohibition. But without the
full ToS text or a single real odds observation, there isn't enough here to
responsibly classify this as anything looser than the same C_ABSTRACT_ONLY
posture as its primary counterpart. If revisited later, get the actual ToS
text and a real rendered odds example first (both require a working browser
engine — plain HTTP was not enough for either).

`is_available()` always returns False; the fetch method raises. Never wire
fabricated odds in its place.
"""

from app.models.enums import DataSourceCategory
from app.providers.base.dto import OddsQuoteRecord
from app.providers.base.odds_provider import OddsProvider

LIVESCORE_BOOKMAKER_LABEL = "livescore.com (fonte quote non verificata)"


class LivescoreOddsProvider(OddsProvider):
    source_key = "livescore_com"
    category = DataSourceCategory.C_ABSTRACT_ONLY
    bookmaker_name = LIVESCORE_BOOKMAKER_LABEL

    def is_available(self) -> bool:
        return False  # verified blocker — see module docstring

    def get_odds_for_match(
        self, home_team_name: str, away_team_name: str, kickoff_utc_iso: str
    ) -> list[OddsQuoteRecord]:
        raise NotImplementedError(
            "livescore.com odds fetching is not implemented: the real odds sit "
            "behind a country/user-gated affiliate widget system never observed "
            "with real data in this session, its full ToS text was never "
            "retrieved, and this session cannot run a real browser engine "
            "against any external host — see this module's docstring and "
            "DATA_SOURCES.md. Never replace this with fabricated odds."
        )
