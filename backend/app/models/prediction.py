from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import AlertLevel, ModelFamily


class ModelVersion(Base, TimestampMixin):
    """A trained, immutable version of a statistical model.

    Predictions always reference the exact model_version that produced them, so
    backtests can be re-run against a specific historical model rather than
    silently using whatever model is live today (which would leak future
    model improvements into a past evaluation).
    """

    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    family: Mapped[ModelFamily]
    market_category: Mapped[str] = mapped_column(String(64))  # matches MarketCategory value
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), index=True)
    version_label: Mapped[str] = mapped_column(String(32))  # e.g. "2026.09.11-1"
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    training_data_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hyperparameters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AnalysisVersion(Base, TimestampMixin):
    """One full analysis run for a match (the "AGGIORNA ANALISI" snapshot).

    Re-running the analysis creates a new AnalysisVersion rather than mutating the
    previous one, so the UI can diff "what changed" without needing unbounded history
    (old versions can be pruned, keeping only N most recent per match).
    """

    __tablename__ = "analysis_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    trigger: Mapped[str] = mapped_column(String(32))  # "manual_refresh", "scheduled", "initial"
    data_snapshot_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Prediction(Base, TimestampMixin):
    """The model's probability estimate for one market outcome, as of one AnalysisVersion."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_version_id: Mapped[int] = mapped_column(ForeignKey("analysis_versions.id"), index=True)
    market_outcome_id: Mapped[int] = mapped_column(ForeignKey("market_outcomes.id"), index=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"), index=True)

    probability: Mapped[float] = mapped_column(Float)
    fair_odds: Mapped[float] = mapped_column(Float)  # 1 / probability (refined later with margin/calibration)
    bookmaker_odds: Mapped[float | None] = mapped_column(Float, nullable=True)  # best available at compute time
    bookmaker_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)  # EV = p * odds - 1
    uncertainty: Mapped[float] = mapped_column(Float)  # 0..1, higher = less confident
    confidence: Mapped[float] = mapped_column(Float)  # 0..1, data-quality-adjusted confidence


class RiskSelection(Base, TimestampMixin):
    """The precomputed main pick (+2 alternatives) for one risk level (1-10) on one match.

    Exactly one row with rank=1 (main) and two with rank in {2,3} (alternatives) per
    (analysis_version, risk_level). Changing the displayed risk level in the UI only
    changes which RiskSelection rows are shown — it never triggers recomputation.
    """

    __tablename__ = "risk_selections"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_version_id: Mapped[int] = mapped_column(ForeignKey("analysis_versions.id"), index=True)
    risk_level: Mapped[int] = mapped_column(Integer, index=True)  # 1..10
    rank: Mapped[int] = mapped_column(Integer)  # 1 = main selection, 2/3 = alternatives
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"))
    risk_score_raw: Mapped[float] = mapped_column(Float)  # continuous score before bucketing to 1..10
    rationale: Mapped[str] = mapped_column(Text)  # human-readable "why" shown in the UI


class Alert(Base, TimestampMixin):
    """A flagged model/market discrepancy for one prediction."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"), index=True)
    level: Mapped[AlertLevel]
    discrepancy_pct: Mapped[float] = mapped_column(Float)  # (model_implied - market_implied) / market_implied
    explanation: Mapped[str] = mapped_column(Text)
