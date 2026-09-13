"""Tests for RssNewsProvider — generic RSS 2.0 feed parsing against a
SYNTHETIC feed body (no live network in the test suite)."""

from datetime import UTC, datetime

import httpx

from app.providers.rss_news.provider import RssNewsProvider

FEED_URL = "https://example.com/team-news.rss"

SYNTHETIC_FEED = """<?xml version="1.0"?>
<rss version="2.0">
<channel>
  <title>Synthetic FC News</title>
  <item>
    <title>Synthetic United sign new striker</title>
    <description>A transfer update about Synthetic United.</description>
    <link>https://example.com/news/1</link>
    <pubDate>Mon, 10 Mar 2025 09:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Match preview</title>
    <description>Synthetic City prepare for the weekend.</description>
    <link>https://example.com/news/2</link>
    <pubDate>Sun, 09 Mar 2025 09:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Old news about Synthetic United</title>
    <description>Stale item, before the `since` cutoff.</description>
    <link>https://example.com/news/3</link>
    <pubDate>Mon, 01 Jan 2024 09:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Unrelated headline</title>
    <description>No team name mentioned here at all.</description>
    <link>https://example.com/news/4</link>
    <pubDate>Mon, 10 Mar 2025 10:00:00 GMT</pubDate>
  </item>
  <item>
    <title>No date item about Synthetic United</title>
    <description>Missing pubDate entirely.</description>
    <link>https://example.com/news/5</link>
  </item>
</channel>
</rss>
"""


def _mock_client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SYNTHETIC_FEED)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_is_available_is_always_true():
    provider = RssNewsProvider(FEED_URL, http_client=_mock_client())
    assert provider.is_available() is True


def test_get_team_news_filters_by_team_name_and_since_cutoff():
    provider = RssNewsProvider(FEED_URL, http_client=_mock_client())
    since = datetime(2025, 1, 1, tzinfo=UTC)

    items = provider.get_team_news("Synthetic United", since)

    assert len(items) == 1
    item = items[0]
    assert item.headline == "Synthetic United sign new striker"
    assert item.team_name == "Synthetic United"
    assert item.url == "https://example.com/news/1"
    assert item.published_at == datetime(2025, 3, 10, 9, 0, tzinfo=UTC)
    assert item.source_key == "rss_generic"


def test_get_team_news_matches_case_insensitively_in_description():
    provider = RssNewsProvider(FEED_URL, http_client=_mock_client())
    since = datetime(2025, 1, 1, tzinfo=UTC)

    items = provider.get_team_news("synthetic city", since)

    assert len(items) == 1
    assert items[0].headline == "Match preview"


def test_get_team_news_excludes_items_without_a_parseable_date():
    provider = RssNewsProvider(FEED_URL, http_client=_mock_client())
    since = datetime(2020, 1, 1, tzinfo=UTC)

    items = provider.get_team_news("Synthetic United", since)

    headlines = {i.headline for i in items}
    assert "No date item about Synthetic United" not in headlines
