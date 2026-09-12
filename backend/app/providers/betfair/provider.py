"""OddsProvider for the Betfair Exchange Betting API (DATA_SOURCES.md category
`D_OFFICIAL_API_PERSONAL_ACCOUNT`).

**Why this is not an A/B/C source.** Every other `OddsProvider` in this
project (ePlay24, Betson via diretta.it, livescore.com) is a scraped website,
so the question for each was "how much ToS risk, and is it worth it". Betfair
is different in kind: this uses Betfair's own documented Betting API
(`developer.betfair.com`), authenticated as the user's own Betfair account,
exactly the way Betfair expects third-party tools to use it. There is no
scraping and no ToS interpretation to make — the risk categories this
project uses for scraped sources do not apply, hence the new,
distinctly-named `D_OFFICIAL_API_PERSONAL_ACCOUNT` category (see
`app/models/enums.py`) rather than forcing this into A/B/C.

**Betfair is an exchange, not a bookmaker — labelled as such everywhere.**
Prices here are the best currently available *back* price from other
Betfair users betting against each other, not a bookmaker's own quoted
price. `bookmaker_name` is always the literal string
`"Betfair (exchange, dati ritardati 1-180s)"` — never a generic
"bookmaker" and never conflated with a Bet365/Betson-style fixed-odds quote.
Every `OddsQuoteRecord` this provider returns also has
`market_label="1X2 (Betfair back price, ritardo 1-180s)"` for the same
reason, so the distinction survives even if a caller only reads that field.

**Only the free Delayed Application Key tier is used, by design.** A Betfair
Live App Key requires identity verification and a one-off ~£499 activation
fee and is not needed here — this project only wants indicative pre-match
prices for personal analysis, and Delayed data (1-180s behind live) is
sufficient since no in-play/live betting decision is made from it. This
provider never requests or depends on Live-tier access; nothing in this
codebase should ever be changed to require it without the user's explicit,
separate decision (a real money cost).

**Getting a Delayed Application Key is a one-time manual step the user must
do themselves** (log into betfair.com, then either the Accounts API's
`createDeveloperAppKeys` operation or the "Accounts API Demo Tool" at
apps.betfair.com) — this code cannot and does not automate that step. The
resulting App Key, plus the account's own username/password, are read from
environment variables via `app.config.Settings`
(`betfair_app_key`/`betfair_username`/`betfair_password`), never hardcoded or
logged — same standard already used for `API_FOOTBALL_KEY`.

**Login method: Interactive Login, not the certificate-based "bot" login.**
Betfair documents two ways to obtain a session token: Interactive Login
(`identitysso.betfair.<tld>/api/login`, just an App Key header + username/
password) and Non-Interactive/"bot" Login (`identitysso-cert.betfair.<tld>`),
which requires generating and uploading a self-signed SSL certificate to the
account first, and is what Betfair recommends for unattended/bot use. This
provider deliberately uses Interactive Login instead: this project calls the
API intermittently for personal pre-match analysis, not as a high-frequency
trading bot, so the extra certificate-management complexity was judged not
worth it for this use case — a real engineering trade-off, not an oversight.
**Correction from an earlier assumption in this file, found only by reading
`betfairlightweight`'s installed source directly**: `APIClient` does *not*
auto-select interactive login when no cert is supplied — `client.login()` is
always the cert-based `Login` endpoint (posts to `identitysso-cert...`),
while interactive login is a distinct, separately-callable endpoint,
`client.login_interactive()` (posts to `identitysso...`). This provider
calls `login_interactive()` explicitly; calling `login()` here would have
silently hit the wrong endpoint.

**Locale: Italian exchange (`.it`), per the user's own account.**
`APIClient(..., locale="italy")` routes identity/keep-alive calls to
`identitysso.betfair.it` instead of the default `.com` — `betfairlightweight`
looks this up from a fixed dict of Betfair-supported locales (`italy` is one
of the few with a distinct TLD; most countries share the `.com` exchange),
confirmed directly from the installed library's `BaseClient.IDENTITY_URLS`.
The Betting API itself (`api.betfair.com`) has no country-specific variant.

**Session-token renewal — verified from the library's own source, not
assumed.** `BaseClient.SESSION_TIMEOUT` gives the Italian exchange a 20-minute
(1200s) token lifetime; `client.session_expired` (a property) returns `True`
once more than half that time (10 minutes) has passed since the last
login/keep-alive — this is `betfairlightweight`'s own built-in cadence
recommendation, not a number invented for this project. `_ensure_client()`
checks this on every call and renews via the cheap `client.keep_alive()`
Identity-API call (same session, no fresh credentials needed) rather than a
full re-login; only if `keep_alive()` itself fails (e.g. the token is too
stale to renew) does it fall back to a full `login_interactive()`. Net
effect: the user never has to re-enter anything manually — this provider
re-authenticates itself transparently for as long as the process runs.

**Not exercised against the live API in this session.** Betfair credentials
*are* configured (env vars), but this sandboxed environment's own egress is
blocked at the network level by Betfair/Cloudflare itself ("Restricted... a
country that Betfair does not accept bets from or... unusual traffic") —
verified live with both placeholder and real credentials, same HTTP 403
non-JSON block page either time, confirmed by the user to work from their
own Italian residential IP. So this is an environment limitation, not a
credentials or code problem (see DATA_SOURCES.md, RUNNING_LOCALLY.md). The
request-building logic below (event type → market catalogue → market book,
team-name/runner-name matching, price extraction) is unit-tested against a
fake client built from betfairlightweight's own documented method signatures
and resource classes (see tests/test_betfair_provider.py), using response
shapes as documented/observed by the user, not invented. A real end-to-end
run against live Betfair data must be done from a non-blocked network (see
RUNNING_LOCALLY.md) before this is trusted for real analysis.

**Market coverage — verified in code/library terms, NOT independently
confirmed live in this session:** this provider fetches both `MATCH_ODDS`
(1X2) and `OVER_UNDER_25` (Over/Under 2.5 goals) — both real, documented
Betfair Exchange market-type codes for football, with the standard runner
naming Betfair uses for each (`"The Draw"`/team names for `MATCH_ODDS`;
`"Over 2.5 Goals"`/`"Under 2.5 Goals"` for `OVER_UNDER_25`). Whether a given
Premier League/Serie A fixture actually has a *tradable, liquid* market this
far out — and specifically whether corners/cards have any Exchange market at
all — was NOT verifiable live this session (network-blocked, see above);
community/secondary-source knowledge says 1X2 markets are commonly created
days ahead with thin early liquidity, but this is not an official Betfair
guarantee. **Corners/cards are deliberately NOT implemented here**: no
verified, real Betfair market-type code for these was confirmed in this
session (unlike `MATCH_ODDS`/`OVER_UNDER_25`, which are extensively
documented), and guessing one would be exactly the "invented data source"
failure this project avoids — this needs live verification (RUNNING_LOCALLY.md)
before being added. If a market for a given fixture does not exist or has no
back price, this provider returns nothing for that outcome, never a
fabricated price.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from betfairlightweight import APIClient, filters

from app.config import settings
from app.core.rate_limiter import RateLimiter
from app.models.enums import DataSourceCategory
from app.providers.base.dto import OddsQuoteRecord
from app.providers.base.odds_provider import OddsProvider

logger = logging.getLogger(__name__)

BETFAIR_BOOKMAKER_LABEL = "Betfair (exchange, dati ritardati 1-180s)"
MATCH_ODDS_MARKET_LABEL = "1X2 (Betfair back price, ritardo 1-180s)"
MATCH_ODDS_MARKET_TYPE_CODE = "MATCH_ODDS"
OVER_UNDER_25_MARKET_LABEL = "Over/Under 2.5 (Betfair back price, ritardo 1-180s)"
OVER_UNDER_25_MARKET_TYPE_CODE = "OVER_UNDER_25"
SOCCER_EVENT_TYPE_NAME = "Soccer"
BETFAIR_ITALY_LOCALE = "italy"


class BetfairCredentialsMissingError(RuntimeError):
    pass


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _match_odds_outcome_code_for(
    runner_name: str, home_team_name: str, away_team_name: str
) -> str | None:
    name_lower = runner_name.strip().lower()
    if name_lower in ("the draw", "draw"):
        return "DRAW"
    if name_lower == home_team_name.strip().lower():
        return "HOME"
    if name_lower == away_team_name.strip().lower():
        return "AWAY"
    return None


def _over_under_25_outcome_code_for(runner_name: str, *_ignored: str) -> str | None:
    """Betfair's `OVER_UNDER_25` market always names its two runners "Over 2.5
    Goals" / "Under 2.5 Goals" (no team names involved, unlike MATCH_ODDS), so
    a simple substring check is robust rather than fragile — this is the
    standard runner-naming convention across all of Betfair's OVER_UNDER_XX
    market family, not guessed for this project specifically. Extra
    `*_ignored` args let this share a call signature with
    `_match_odds_outcome_code_for` in `_fetch_market_odds` below."""
    name_lower = runner_name.strip().lower()
    if "over" in name_lower:
        return "OVER"
    if "under" in name_lower:
        return "UNDER"
    return None


class BetfairExchangeOddsProvider(OddsProvider):
    source_key = "betfair_exchange"
    category = DataSourceCategory.D_OFFICIAL_API_PERSONAL_ACCOUNT
    bookmaker_name = BETFAIR_BOOKMAKER_LABEL

    def __init__(
        self,
        app_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        client: APIClient | None = None,
    ) -> None:
        self._app_key = app_key or settings.betfair_app_key
        self._username = username or settings.betfair_username
        self._password = password or settings.betfair_password
        self._client = client
        self._logged_in = False
        self._soccer_event_type_id: str | None = None
        # No documented numeric rate limit for the Betting API's read
        # operations was found in this session (see DATA_SOURCES.md) — this
        # is a conservative, self-imposed budget, not a published Betfair figure.
        self._rate_limiter = RateLimiter(max_calls=30, period_seconds=60.0)

    def is_available(self) -> bool:
        return bool(self._app_key and self._username and self._password)

    def _ensure_client(self) -> APIClient:
        if not self.is_available():
            raise BetfairCredentialsMissingError(
                "BetfairExchangeOddsProvider requires betfair_app_key/betfair_username/"
                "betfair_password (env vars, or constructor args) — a free Delayed "
                "Application Key from a Betfair account, never the paid Live key. "
                "See DATA_SOURCES.md for how to obtain one."
            )
        if self._client is None:
            self._client = APIClient(
                username=self._username,
                password=self._password,
                app_key=self._app_key,
                locale=BETFAIR_ITALY_LOCALE,
            )
        if not self._logged_in:
            self._rate_limiter.acquire()
            # Interactive Login, not the cert-based `client.login()` — see
            # module docstring for why these are two distinct endpoints.
            self._client.login_interactive()
            self._logged_in = True
        elif self._client.session_expired:
            self._rate_limiter.acquire()
            try:
                self._client.keep_alive()
            except Exception:  # noqa: BLE001 -- any keep_alive failure must fall back to a
                # full re-login rather than propagate, since the caller just wants a
                # working session and doesn't care which of the two renewal paths got it there.
                logger.info(
                    "Betfair keep_alive failed (session likely too stale to renew) — "
                    "falling back to a full re-login."
                )
                self._client.login_interactive()
        return self._client

    def _get_soccer_event_type_id(self, client: APIClient) -> str:
        if self._soccer_event_type_id is None:
            self._rate_limiter.acquire()
            results = client.betting.list_event_types()
            match = next(
                (r for r in results if r.event_type.name == SOCCER_EVENT_TYPE_NAME), None
            )
            if match is None:
                raise ValueError(
                    f"Betfair listEventTypes did not return a {SOCCER_EVENT_TYPE_NAME!r} "
                    "event type in this response — cannot search for football markets."
                )
            self._soccer_event_type_id = match.event_type.id
        return self._soccer_event_type_id

    def get_odds_for_match(
        self, home_team_name: str, away_team_name: str, kickoff_utc_iso: str
    ) -> list[OddsQuoteRecord]:
        client = self._ensure_client()
        soccer_id = self._get_soccer_event_type_id(client)
        kickoff = _parse_iso(kickoff_utc_iso)

        records = self._fetch_market_odds(
            client,
            soccer_id,
            home_team_name,
            away_team_name,
            kickoff,
            market_type_code=MATCH_ODDS_MARKET_TYPE_CODE,
            market_label=MATCH_ODDS_MARKET_LABEL,
            outcome_mapper=_match_odds_outcome_code_for,
        )
        records += self._fetch_market_odds(
            client,
            soccer_id,
            home_team_name,
            away_team_name,
            kickoff,
            market_type_code=OVER_UNDER_25_MARKET_TYPE_CODE,
            market_label=OVER_UNDER_25_MARKET_LABEL,
            outcome_mapper=_over_under_25_outcome_code_for,
        )
        return records

    def _fetch_market_odds(
        self,
        client: APIClient,
        soccer_id: str,
        home_team_name: str,
        away_team_name: str,
        kickoff: datetime,
        *,
        market_type_code: str,
        market_label: str,
        outcome_mapper: Callable[[str, str, str], str | None],
    ) -> list[OddsQuoteRecord]:
        """Shared catalogue -> book -> price-extraction flow for one Betfair
        market type. `MATCH_ODDS` and `OVER_UNDER_25` differ only in which
        market type is searched for and how a runner name maps to our
        outcome_code — everything else (event/team matching, rate limiting,
        never fabricating a price) is identical, so this is factored out
        rather than duplicated per market."""
        window_from = kickoff - timedelta(hours=12)
        window_to = kickoff + timedelta(hours=12)

        self._rate_limiter.acquire()
        catalogues = client.betting.list_market_catalogue(
            filter=filters.market_filter(
                event_type_ids=[soccer_id],
                market_type_codes=[market_type_code],
                text_query=f"{home_team_name} v {away_team_name}",
                market_start_time={
                    "from": window_from.isoformat(),
                    "to": window_to.isoformat(),
                },
            ),
            market_projection=["RUNNER_DESCRIPTION", "EVENT"],
            max_results=10,
        )

        home_lower = home_team_name.strip().lower()
        away_lower = away_team_name.strip().lower()
        market = next(
            (
                m
                for m in catalogues
                if home_lower in m.event.name.lower() and away_lower in m.event.name.lower()
            ),
            None,
        )
        if market is None:
            return []  # no tradable market of this type found — never fabricate one

        selection_to_runner_name = {r.selection_id: r.runner_name for r in market.runners}

        self._rate_limiter.acquire()
        books = client.betting.list_market_book(
            market_ids=[market.market_id],
            price_projection=filters.price_projection(price_data=["EX_BEST_OFFERS"]),
        )
        if not books:
            return []
        book = books[0]

        now = datetime.now(UTC)
        records = []
        for runner in book.runners:
            if not runner.ex or not runner.ex.available_to_back:
                continue  # no back price currently available for this runner
            runner_name = selection_to_runner_name.get(runner.selection_id)
            if runner_name is None:
                continue
            outcome_code = outcome_mapper(runner_name, home_team_name, away_team_name)
            if outcome_code is None:
                continue
            best_back = runner.ex.available_to_back[0]
            records.append(
                OddsQuoteRecord(
                    bookmaker=BETFAIR_BOOKMAKER_LABEL,
                    market_label=market_label,
                    outcome_code=outcome_code,
                    decimal_odds=best_back.price,
                    captured_at=now,
                    is_closing=False,
                )
            )
        return records
