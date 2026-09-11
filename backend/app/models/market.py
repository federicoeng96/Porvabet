from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import MarketCategory


class Market(Base, TimestampMixin):
    """A specific market offered on a match, e.g. '1X2', 'Over/Under 2.5', 'Player X shots O/U 1.5'."""

    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    category: Mapped[MarketCategory] = mapped_column(index=True)
    # Optional subject: player-prop markets reference a player; team-specific
    # markets (e.g. team total corners) reference a team.
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    # The market's line/handicap where applicable (e.g. 2.5 for O/U 2.5, -1 for handicap).
    line: Mapped[float | None] = mapped_column(Float, nullable=True)
    label: Mapped[str] = mapped_column(String(128))  # human-readable, e.g. "Over/Under 2.5 goals"


class MarketOutcome(Base, TimestampMixin):
    """A single bettable outcome within a market, e.g. HOME / DRAW / AWAY, OVER / UNDER."""

    __tablename__ = "market_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), index=True)
    code: Mapped[str] = mapped_column(String(32))  # "HOME", "DRAW", "AWAY", "OVER", "UNDER", "YES", "NO"
    label: Mapped[str] = mapped_column(String(128))


class OddsQuote(Base, TimestampMixin):
    """A single bookmaker odds observation for a market outcome at a point in time.

    Historical closing odds from football-data.co.uk populate this at match-level
    granularity (one closing quote per bookmaker per outcome); a live OddsProvider
    (e.g. ePlay24, if/when accessible) would populate it with a time series.
    """

    __tablename__ = "odds"

    id: Mapped[int] = mapped_column(primary_key=True)
    market_outcome_id: Mapped[int] = mapped_column(ForeignKey("market_outcomes.id"), index=True)
    bookmaker: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "eplay24", "bet365", "pinnacle"
    decimal_odds: Mapped[float] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    is_closing: Mapped[bool] = mapped_column(default=False)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
