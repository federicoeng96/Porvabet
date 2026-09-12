"""Persist a completed backtest run into the `backtests` table.

Until now, every real backtest run in this project (walk-forward goals/1X2/O-U
via `app.backtest.runner`, corners/cards via `app.backtest.count_market_runner`)
was executed with an ad-hoc script and the numbers were copied by hand into
BACKTEST_SPEC.md (see ROADMAP.md item 1). That is fine for a one-off report,
but it means the DB's own `Backtest`/`ModelVersion` tables — built precisely to
let `model_reliability` in the live analysis endpoint reference a *real*,
persisted backtest instead of a neutral placeholder — have never actually been
populated with real data.

This module is the missing aggregation step: it takes the resolved predictions
already produced by a backtest runner (converted to `BetRecord`, exactly as
`app.backtest.metrics` expects), computes the same metrics BACKTEST_SPEC.md
reports, and writes one `ModelVersion` + one `Backtest` row.

One caveat worth stating plainly (not hidden in a docstring nobody reads): a
walk-forward backtest refits the model many times over the window (see
`REFIT_BATCH_DAYS` in the runners), so there is no single "trained_at" /
"training_data_cutoff" moment the way there is for one production model fit.
`ModelVersion.training_data_cutoff` here is set to the backtest window's end
date and `notes` says so explicitly — it documents which backtest run this
metadata describes, not a claim that the model was fit once at that instant.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.backtest.metrics import (
    BetRecord,
    brier_score,
    calibration_curve,
    hit_rate,
    log_loss,
    profit_units,
    roi,
    yield_pct,
)
from app.models.backtest import Backtest
from app.models.enums import ModelFamily
from app.models.prediction import ModelVersion


def persist_backtest_run(
    session: Session,
    *,
    bets: list[BetRecord],
    model_family: ModelFamily,
    market_category: str,
    competition_id: int,
    version_label: str,
    window_start: date,
    window_end: date,
    hyperparameters: dict | None = None,
    notes: str | None = None,
    leakage_check_notes: str | None = None,
) -> Backtest:
    """Aggregate already-resolved `bets` into one `ModelVersion` + `Backtest` row.

    `bets` must be the full set of resolved predictions for exactly one
    (model_family, market_category, competition) segment — the same
    granularity BACKTEST_SPEC.md reports per-segment metrics at. Callers
    filter/convert a runner's output into `BetRecord`s before calling this;
    this function does not know how a prediction was produced, only how to
    score and store the outcome (same separation of concerns as metrics.py).
    """
    if not bets:
        raise ValueError("cannot persist a backtest run with zero resolved predictions")

    run_at = datetime.now(UTC)
    model_version = ModelVersion(
        family=model_family,
        market_category=market_category,
        competition_id=competition_id,
        version_label=version_label,
        trained_at=run_at,
        training_data_cutoff=datetime(window_end.year, window_end.month, window_end.day, tzinfo=UTC),
        hyperparameters_json=json.dumps(hyperparameters) if hyperparameters is not None else None,
        notes=notes,
    )
    session.add(model_version)
    session.flush()  # need model_version.id before building the Backtest row

    metrics_payload = {
        "calibration_curve": [
            {
                "bin_low": b.bin_low,
                "bin_high": b.bin_high,
                "predicted_mean": b.predicted_mean,
                "observed_frequency": b.observed_frequency,
                "count": b.count,
            }
            for b in calibration_curve(bets)
        ],
    }

    backtest = Backtest(
        model_version_id=model_version.id,
        window_start=window_start,
        window_end=window_end,
        run_at=run_at,
        n_predictions=len(bets),
        hit_rate=hit_rate(bets),
        roi=roi(bets),
        yield_pct=yield_pct(bets),
        profit_units=profit_units(bets),
        brier_score=brier_score(bets),
        log_loss=log_loss(bets),
        metrics_json=json.dumps(metrics_payload),
        leakage_check_notes=leakage_check_notes,
    )
    session.add(backtest)
    session.flush()
    return backtest
