"""Leak-free evaluation of post-hoc calibration (Platt/isotonic — see
`app/engine/decision/calibration.py`) on top of an already-run walk-forward
backtest (ROADMAP.md "Calibrazione dei pesi/soglie/probabilità").

Fitting a calibrator on the same predictions it is then scored on would leak
exactly the kind of information the walk-forward backtest itself is careful
to avoid (see `app/backtest/runner.py` / `count_market_runner.py` docstrings).
So this module splits an already time-ordered list of `BetRecord`s into an
earlier portion (fits the calibrator) and a later, held-out portion
(evaluates it) — the same "never see the future" discipline, just applied one
step further down the pipeline.

**Precondition**: `bets` must already be sorted by the underlying match date,
ascending. `BetRecord` itself carries no date field (by design — see
`app/backtest/metrics.py`, kept a pure scoring type that doesn't know how a
prediction was produced), so this module trusts the caller to supply it in
time order, exactly as the walk-forward runners naturally produce it.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from app.backtest.metrics import (
    BetRecord,
    CalibrationBin,
    brier_score,
    calibration_curve,
    hit_rate,
    log_loss,
)
from app.engine.decision.calibration import (
    IsotonicCalibrator,
    PlattCalibrator,
    fit_isotonic_calibration,
    fit_platt_calibration,
)


@dataclass(frozen=True)
class CalibrationComparisonResult:
    n_train: int
    n_test: int
    platt: PlattCalibrator
    isotonic: IsotonicCalibrator
    raw_hit_rate: float | None
    raw_brier: float | None
    raw_log_loss: float | None
    raw_calibration_curve: list[CalibrationBin]
    platt_brier: float | None
    platt_log_loss: float | None
    platt_calibration_curve: list[CalibrationBin]
    isotonic_brier: float | None
    isotonic_log_loss: float | None
    isotonic_calibration_curve: list[CalibrationBin]


def evaluate_calibration(bets_in_time_order: list[BetRecord], test_fraction: float = 0.2) -> CalibrationComparisonResult:
    n = len(bets_in_time_order)
    split = int(n * (1 - test_fraction))
    train, test = bets_in_time_order[:split], bets_in_time_order[split:]

    platt = fit_platt_calibration(train)
    isotonic = fit_isotonic_calibration(train)

    platt_test = [dataclasses.replace(b, probability=platt.calibrate(b.probability)) for b in test]
    isotonic_test = [dataclasses.replace(b, probability=isotonic.calibrate(b.probability)) for b in test]

    return CalibrationComparisonResult(
        n_train=len(train),
        n_test=len(test),
        platt=platt,
        isotonic=isotonic,
        raw_hit_rate=hit_rate(test),
        raw_brier=brier_score(test),
        raw_log_loss=log_loss(test),
        raw_calibration_curve=calibration_curve(test),
        platt_brier=brier_score(platt_test),
        platt_log_loss=log_loss(platt_test),
        platt_calibration_curve=calibration_curve(platt_test),
        isotonic_brier=brier_score(isotonic_test),
        isotonic_log_loss=log_loss(isotonic_test),
        isotonic_calibration_curve=calibration_curve(isotonic_test),
    )
