from datetime import date, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Backtest(Base, TimestampMixin):
    """One backtest run of a model_version over a historical window.

    Metrics are stored as a JSON blob (`metrics_json`) keyed by segment — see
    BACKTEST_SPEC.md for the exact schema (overall, per risk level, per market,
    home/away, per value bucket, calibration curve points, etc.) — because the
    metric set is defined by BACKTEST_SPEC.md and evolves independently of the schema.
    """

    __tablename__ = "backtests"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"), index=True)
    window_start: Mapped[date]
    window_end: Mapped[date]
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    n_predictions: Mapped[int] = mapped_column(Integer)
    hit_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    roi: Mapped[float | None] = mapped_column(Float, nullable=True)
    yield_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_units: Mapped[float | None] = mapped_column(Float, nullable=True)
    brier_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    log_loss: Mapped[float | None] = mapped_column(Float, nullable=True)

    metrics_json: Mapped[str] = mapped_column(Text)  # full breakdown, see BACKTEST_SPEC.md
    leakage_check_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
