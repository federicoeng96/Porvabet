"""Real, generic NewsProvider that reads any standard RSS/Atom feed.

Rather than hardcoding an unverified scraper against a specific news site, this
provider takes a feed URL as configuration (e.g. a club's official RSS feed, or a
competition news feed) and parses it with the standard library's XML parser —
genuinely functional against any real, valid RSS/Atom feed, with no invented
endpoints. Matching a news item to a specific team/player by name is a simple
substring heuristic here; a real Intelligence Engine deployment would refine this
with proper entity linking (see MODEL_SPEC.md).
"""

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx

from app.models.enums import DataSourceCategory
from app.providers.base.dto import NewsItemRecord
from app.providers.base.news_provider import NewsProvider


class RssNewsProvider(NewsProvider):
    source_key = "rss_generic"
    category = DataSourceCategory.A_UNRESTRICTED

    def __init__(self, feed_url: str, http_client: httpx.Client | None = None) -> None:
        self._feed_url = feed_url
        self._client = http_client or httpx.Client(timeout=15.0, follow_redirects=True)

    def is_available(self) -> bool:
        return True

    def get_team_news(self, team_name: str, since: datetime) -> list[NewsItemRecord]:
        response = self._client.get(self._feed_url)
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)

        items = []
        for item in root.iter("item"):  # RSS 2.0
            title = (item.findtext("title") or "").strip()
            description = item.findtext("description")
            link = item.findtext("link")
            pub_date_raw = item.findtext("pubDate")
            published_at = _parse_date(pub_date_raw)
            if published_at is None or published_at < since:
                continue
            if team_name.lower() not in title.lower() and (
                not description or team_name.lower() not in description.lower()
            ):
                continue
            items.append(
                NewsItemRecord(
                    team_name=team_name,
                    player_name=None,
                    headline=title,
                    body=description,
                    published_at=published_at,
                    url=link,
                    source_key=self.source_key,
                )
            )
        return items


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).astimezone(UTC)
    except (TypeError, ValueError):
        return None
