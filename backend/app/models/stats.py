from datetime import date

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class TeamMatchStats(Base, TimestampMixin):
    """Observed per-match team stats, used to fit opponent-adjusted rolling features.

    One row per (match, team) — never read by the pre-match feature builder for the
    same match it belongs to; only used to build rolling/historical features for
    *future* matches of that team.
    """

    __tablename__ = "team_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    is_home: Mapped[bool] = mapped_column(default=True)

    shots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots_on_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    corners: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fouls_committed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yellow_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    red_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    possession_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    xg: Mapped[float | None] = mapped_column(Float, nullable=True)
    xga: Mapped[float | None] = mapped_column(Float, nullable=True)

    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)


class PlayerMatchStats(Base, TimestampMixin):
    __tablename__ = "player_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)

    minutes_played: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assists: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots_on_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    key_passes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fouls_committed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fouls_suffered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yellow_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    red_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)


class TacticalFeature(Base, TimestampMixin):
    """A single measurable tactical feature for a team (or player) as of a given date.

    Snapshot table: one row per (subject, feature_name, as_of_date) so pre-match feature
    lookups can filter `as_of_date < match.kickoff_utc` and never see future information.
    """

    __tablename__ = "tactical_features"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True, index=True)
    as_of_date: Mapped[date] = mapped_column(index=True)
    feature_name: Mapped[str] = mapped_column(String(64), index=True)
    # e.g. crosses_per_90, ppda, progressive_passes_per_90, corners_for_per_90, ...
    value: Mapped[float] = mapped_column(Float)
    window_matches: Mapped[int] = mapped_column(Integer, default=10)
    opponent_adjusted: Mapped[bool] = mapped_column(default=False)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)


class RefereeStats(Base, TimestampMixin):
    __tablename__ = "referee_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    referee_id: Mapped[int] = mapped_column(ForeignKey("referees.id"), index=True)
    as_of_date: Mapped[date] = mapped_column(index=True)
    matches_officiated: Mapped[int] = mapped_column(Integer)
    avg_fouls_per_match: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_yellow_cards_per_match: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_red_cards_per_match: Mapped[float | None] = mapped_column(Float, nullable=True)
    penalties_awarded_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)


class Weather(Base, TimestampMixin):
    __tablename__ = "weather"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), unique=True, index=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_kph: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    condition: Mapped[str | None] = mapped_column(String(32), nullable=True)  # e.g. "rain", "clear"
    forecast_at: Mapped[date] = mapped_column()
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
