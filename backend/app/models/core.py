from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import DataSourceCategory


class Source(Base, TimestampMixin):
    """A data provider registered in the system (see DATA_SOURCES.md)."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # e.g. "football_data_co_uk"
    name: Mapped[str] = mapped_column(String(128))
    category: Mapped[DataSourceCategory] = mapped_column(default=DataSourceCategory.C_ABSTRACT_ONLY)
    is_implemented: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Competition(Base, TimestampMixin):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)  # "EPL", "SERIE_A"
    name: Mapped[str] = mapped_column(String(128))
    country: Mapped[str] = mapped_column(String(64))
    tier: Mapped[int] = mapped_column(default=1)

    seasons: Mapped[list["Season"]] = relationship(back_populates="competition")


class Season(Base, TimestampMixin):
    __tablename__ = "seasons"
    __table_args__ = (UniqueConstraint("competition_id", "label", name="uq_season_competition_label"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), index=True)
    label: Mapped[str] = mapped_column(String(16))  # "2024/2025"
    start_date: Mapped[date]
    end_date: Mapped[date]

    competition: Mapped["Competition"] = relationship(back_populates="seasons")


class Team(Base, TimestampMixin):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    short_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Canonical key used to reconcile the same club across providers with different naming
    # (e.g. football-data.co.uk "Man United" vs API-Football "Manchester United").
    canonical_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Coach(Base, TimestampMixin):
    __tablename__ = "coaches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    canonical_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)


class Player(Base, TimestampMixin):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    canonical_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    position: Mapped[str | None] = mapped_column(String(32), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Referee(Base, TimestampMixin):
    __tablename__ = "referees"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    canonical_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
