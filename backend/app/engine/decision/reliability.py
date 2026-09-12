"""Real, backtest-derived `model_reliability` (see `risk_score.RiskFactors`).

Replaces the fixed `model_reliability=0.5` placeholder previously hardcoded in
`analysis_runner.py` with an estimate read from the most recently persisted
`Backtest` row (`app/backtest/persistence.py`) for the same
(model_family, market_category, competition) — real data already sitting in
the DB, not a guess.

**Why calibration gap, not Brier score / log loss / hit rate.** All four are
available on every persisted `Backtest` row, but they measure different
things. Brier score and log loss blend discrimination (does the model tell
strong matches from close ones) with calibration (when it says 70%, does 70%
actually happen). Hit rate additionally depends on which candidate the risk
ladder happened to select, not the raw probability. `model_reliability` here
answers one specific question — "can this probability, this specific number,
be trusted at face value" — and the calibration curve (`predicted_mean` vs
`observed_frequency` per bin, already stored in `Backtest.metrics_json`) is
the one metric that directly measures exactly that. BACKTEST_SPEC.md's own
findings (systematic overconfidence concentrated in the high-probability
bins, for both goals and corners/cards) are a calibration problem, not a
discrimination problem — using Brier/log loss here would dilute the signal
with something the data doesn't actually show is broken. Blending all four
into one number with made-up weights would trade one placeholder for another
kind of arbitrary constant, which is exactly what this replaces.

**Bin-local first, segment-level fallback, honest "not estimable" as a last
resort.** A candidate's own probability is looked up in its market's
calibration curve; if that specific bin has too few observations to trust
(`MIN_BIN_COUNT`), reliability falls back to a count-weighted average gap
over whichever bins in the segment do have enough data. If literally no bin
in the segment clears the threshold, this returns `None` rather than forcing
a number — see `analysis_runner.py` for how the risk engine treats that case.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.backtest import Backtest
from app.models.enums import ModelFamily
from app.models.prediction import ModelVersion

# A bin below this count is too noisy to anchor a single reliability number on
# (see BACKTEST_SPEC.md: the Serie A goals 0.9-1.0 bin has n=38, already at this
# edge, and its calibration gap swings ~19 points — exactly the kind of bin this
# threshold is meant to distrust on its own).
MIN_BIN_COUNT = 30


@dataclass(frozen=True)
class ReliabilityEstimate:
    value: float | None  # None = not estimable with confidence (see module docstring)
    source_backtest_id: int | None
    detail: str  # human-readable justification (which bin(s), n, gap) for auditability


def model_reliability_for(
    db: Session,
    model_family: ModelFamily,
    market_category: str,
    competition_id: int,
    probability: float,
) -> ReliabilityEstimate:
    backtest = _latest_backtest(db, model_family, market_category, competition_id)
    if backtest is None:
        return ReliabilityEstimate(
            value=None,
            source_backtest_id=None,
            detail=(
                f"no persisted Backtest for family={model_family.value} "
                f"market_category={market_category} competition_id={competition_id}"
            ),
        )

    bins = json.loads(backtest.metrics_json).get("calibration_curve", [])
    local_bin = _find_bin(bins, probability)
    if local_bin is not None and local_bin["count"] >= MIN_BIN_COUNT:
        gap = abs(local_bin["predicted_mean"] - local_bin["observed_frequency"])
        return ReliabilityEstimate(
            value=max(0.0, 1.0 - gap),
            source_backtest_id=backtest.id,
            detail=(
                f"bin [{local_bin['bin_low']:.1f},{local_bin['bin_high']:.1f}) "
                f"n={local_bin['count']} gap={gap:.3f} (backtest id={backtest.id})"
            ),
        )

    usable = [b for b in bins if b["count"] and b["count"] >= MIN_BIN_COUNT]
    if not usable:
        return ReliabilityEstimate(
            value=None,
            source_backtest_id=backtest.id,
            detail=(
                f"backtest id={backtest.id}: no calibration bin has >= {MIN_BIN_COUNT} "
                "observations — reliability not estimable with confidence for this segment"
            ),
        )

    total = sum(b["count"] for b in usable)
    weighted_gap = sum(abs(b["predicted_mean"] - b["observed_frequency"]) * b["count"] for b in usable) / total
    return ReliabilityEstimate(
        value=max(0.0, 1.0 - weighted_gap),
        source_backtest_id=backtest.id,
        detail=(
            f"segment-level average over {len(usable)} bins (n={total}), "
            f"gap={weighted_gap:.3f} (backtest id={backtest.id}, candidate probability "
            f"{probability:.3f} fell in a bin with < {MIN_BIN_COUNT} observations)"
        ),
    )


def _latest_backtest(
    db: Session, model_family: ModelFamily, market_category: str, competition_id: int
) -> Backtest | None:
    return db.scalar(
        select(Backtest)
        .join(ModelVersion, Backtest.model_version_id == ModelVersion.id)
        .where(
            ModelVersion.family == model_family,
            ModelVersion.market_category == market_category,
            ModelVersion.competition_id == competition_id,
        )
        .order_by(Backtest.run_at.desc())
        .limit(1)
    )


def _find_bin(bins: list[dict], probability: float) -> dict | None:
    for b in bins:
        if b["count"] and b["bin_low"] <= probability < b["bin_high"]:
            return b
    # last bin is closed on both ends (probability == 1.0 falls here) —
    # mirrors app.backtest.metrics.calibration_curve's own bin-edge handling.
    if bins and probability == 1.0 and bins[-1]["count"]:
        return bins[-1]
    return None
