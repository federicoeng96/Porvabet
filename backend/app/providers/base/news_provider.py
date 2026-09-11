from abc import ABC, abstractmethod
from datetime import datetime

from app.models.enums import DataSourceCategory
from app.providers.base.dto import NewsItemRecord


class NewsProvider(ABC):
    """A source of team/player news feeding the Intelligence Engine's qualitative signals."""

    source_key: str
    category: DataSourceCategory

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def get_team_news(self, team_name: str, since: datetime) -> list[NewsItemRecord]: ...
