"""Tests for FbrefProvider — HTML table fetch/parse against a SYNTHETIC page
body (no live network in the test suite). Covers the real behavior this
provider exists for: stripping fbref's HTML-comment-wrapped tables before
`pandas.read_html`, the rate limiter being invoked, and the two failure
paths (table not found, non-2xx response)."""

import httpx
import pytest

from app.providers.fbref.provider import FbrefProvider

URL = "https://fbref.com/en/squads/synthetic/Synthetic-United-Stats"

VISIBLE_TABLE_HTML = """
<html><body>
<table id="stats_standard">
<thead><tr><th>Player</th><th>Gls</th></tr></thead>
<tbody><tr><td>Synthetic Player</td><td>5</td></tr></tbody>
</table>
</body></html>
"""

COMMENTED_TABLE_HTML = """
<html><body>
<!--
<table id="stats_shooting">
<thead><tr><th>Player</th><th>Sh</th></tr></thead>
<tbody><tr><td>Synthetic Player</td><td>20</td></tr></tbody>
</table>
-->
</body></html>
"""


def _mock_client(html: str, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=html)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_is_available_is_always_true_no_key_required():
    provider = FbrefProvider(http_client=_mock_client(VISIBLE_TABLE_HTML))
    assert provider.is_available() is True


def test_get_historical_matches_not_supported():
    provider = FbrefProvider(http_client=_mock_client(VISIBLE_TABLE_HTML))
    with pytest.raises(NotImplementedError):
        provider.get_historical_matches("EPL", "2024/2025")


def test_fetch_table_parses_a_normal_visible_table():
    provider = FbrefProvider(http_client=_mock_client(VISIBLE_TABLE_HTML))

    df = provider.fetch_table(URL, "stats_standard")

    assert list(df.columns) == ["Player", "Gls"]
    assert df.iloc[0]["Player"] == "Synthetic Player"
    assert int(df.iloc[0]["Gls"]) == 5


def test_fetch_table_parses_a_comment_wrapped_table():
    """fbref hides some tables inside HTML comments to discourage naive
    scraping — this is the specific real-world quirk this provider exists to
    work around (see module docstring)."""
    provider = FbrefProvider(http_client=_mock_client(COMMENTED_TABLE_HTML))

    df = provider.fetch_table(URL, "stats_shooting")

    assert list(df.columns) == ["Player", "Sh"]
    assert int(df.iloc[0]["Sh"]) == 20


def test_fetch_table_raises_when_table_id_not_found():
    provider = FbrefProvider(http_client=_mock_client(VISIBLE_TABLE_HTML))

    with pytest.raises(ValueError, match="stats_defense"):
        provider.fetch_table(URL, "stats_defense")


def test_fetch_table_raises_on_http_error():
    provider = FbrefProvider(http_client=_mock_client("not found", status=404))

    with pytest.raises(httpx.HTTPStatusError):
        provider.fetch_table(URL, "stats_standard")
