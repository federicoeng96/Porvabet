"""Real SportsDataProvider for fbref.com (DATA_SOURCES.md category A).

fbref publishes advanced team/player stats (shots, passing, defensive actions,
per-90 metrics) as plain HTML tables, no key required. Their stated bot-traffic
policy caps requests at 10/minute across the Sports-Reference/Stathead family for
this specific site (exceeding it can get a session temporarily blocked) — enforced
here via `RateLimiter(10, 60)`. This has not been exercised against the live site
in the current sandboxed session (network-restricted); the "10/min" figure and
the HTML-comment quirk below are corroborated by public documentation/tooling,
not a live fetch performed in this session.

fbref renders some tables (typically the "extra" advanced-stat tables beyond the
first one on a page) inside HTML comments, apparently to discourage naive
scraping — `pandas.read_html` skips commented-out tables, so this provider strips
comment markers before parsing.
"""

import re
from io import StringIO

import httpx
import pandas as pd

from app.core.rate_limiter import RateLimiter
from app.models.enums import DataSourceCategory
from app.providers.base.sports_data_provider import SportsDataProvider

BASE_URL = "https://fbref.com"

_COMMENT_PATTERN = re.compile(r"<!--|-->")


class FbrefProvider(SportsDataProvider):
    source_key = "fbref"
    category = DataSourceCategory.A_UNRESTRICTED

    def __init__(self, http_client: httpx.Client | None = None, timeout_s: float = 20.0) -> None:
        self._client = http_client or httpx.Client(timeout=timeout_s, follow_redirects=True)
        self._rate_limiter = RateLimiter(max_calls=10, period_seconds=60.0)

    def is_available(self) -> bool:
        return True

    def get_historical_matches(self, competition_code: str, season_label: str):
        raise NotImplementedError(
            "fbref is used for team/player advanced-stat tables (see fetch_table), "
            "not as a results source — use FootballDataCoUkProvider for results."
        )

    def fetch_table(self, url: str, table_id: str) -> pd.DataFrame:
        """Fetch one named HTML table (by its `id` attribute) from an fbref page."""
        self._rate_limiter.acquire()
        response = self._client.get(url)
        response.raise_for_status()
        html = _COMMENT_PATTERN.sub("", response.text)
        # `pandas.read_html` treats a bare `str` as a filepath/URL, not literal
        # HTML — wrapping in StringIO is required for it to parse `html` directly
        # (found via this session's own test coverage work, not a hypothetical).
        # `flavor="lxml"` is pinned explicitly: with no match for `attrs`, an
        # unpinned flavor falls back to html5lib/bs4 (not installed) and raises
        # a confusing ImportError instead of the clean "no tables found" case
        # this method already handles below.
        try:
            tables = pd.read_html(StringIO(html), attrs={"id": table_id}, flavor="lxml")
        except ValueError as exc:
            # pandas itself raises "No tables found matching regex..." (rather
            # than returning []) when `attrs` matches nothing — re-raised here
            # with the table_id/url this method's caller actually needs to debug.
            raise ValueError(f"Table id={table_id!r} not found at {url}") from exc
        if not tables:
            raise ValueError(f"Table id={table_id!r} not found at {url}")
        return tables[0]
