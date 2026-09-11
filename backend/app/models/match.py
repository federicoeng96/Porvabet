from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import LineupConfidence, MatchStatus

if TYPE_CHECKING:
    from app.models.core import Team


class Match(Base, TimestampMixin):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), index=True)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    referee_id: Mapped[int | None] = mapped_column(ForeignKey("referees.id"), nullable=True)

    kickoff_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    matchday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[MatchStatus] = mapped_column(default=MatchStatus.SCHEDULED)

    # Full-time result, populated only after the match — never read by pre-match feature
    # builders (see ARCHITECTURE.md "no leakage" boundary).
    home_goals_ft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals_ft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_goals_ht: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals_ht: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # External id from the primary sports-data source, for idempotent upserts on re-ingestion.
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    home_team: Mapped["Team"] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped["Team"] = relationship(foreign_keys=[away_team_id])


class Lineup(Base, TimestampMixin):
    """A (possibly probable) lineup for one team in one match."""

    __tablename__ = "lineups"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    formation: Mapped[str | None] = mapped_column(String(16), nullable=True)  # e.g. "4-3-3"
    is_starting: Mapped[bool] = mapped_column(Boolean, default=True)
    shirt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[LineupConfidence] = mapped_column(default=LineupConfidence.UNKNOWN)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Injury(Base, TimestampMixin):
    __tablename__ = "injuries"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    status: Mapped[str] = mapped_column(String(32))  # OUT, DOUBTFUL, SUSPENDED
    reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expected_return: Mapped[date | None] = mapped_column(nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)


class Transfer(Base, TimestampMixin):
    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    from_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    to_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    transfer_date: Mapped[date]
    fee_eur: Mapped[float | None] = mapped_column(nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
