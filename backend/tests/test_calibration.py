"""Tests for Platt scaling and isotonic regression post-hoc calibrators
(ROADMAP.md "Calibrazione dei pesi/soglie/probabilità") — SYNTHETIC data only."""

import random

import pytest

from app.backtest.metrics import BetRecord, brier_score, log_loss
from app.engine.decision.calibration import (
    fit_isotonic_calibration,
    fit_platt_calibration,
)


def _well_calibrated_bets(seed: int = 1, n_per_bin: int = 200) -> list[BetRecord]:
    rng = random.Random(seed)
    bets = []
    for decile in range(10):
        p = decile / 10 + 0.05
        for _ in range(n_per_bin):
            bets.append(BetRecord(probability=p, bookmaker_odds=1.5, won=(rng.random() < p)))
    return bets


def _overconfident_bets(seed: int = 2, n_per_bin: int = 200) -> list[BetRecord]:
    """Raw probability p, but the true win rate is only p * 0.6 — systematic
    overconfidence, same qualitative shape BACKTEST_SPEC.md documents."""
    rng = random.Random(seed)
    bets = []
    for decile in range(10):
        p = decile / 10 + 0.05
        true_rate = p * 0.6
        for _ in range(n_per_bin):
            bets.append(BetRecord(probability=p, bookmaker_odds=1.5, won=(rng.random() < true_rate)))
    return bets


def test_platt_on_well_calibrated_data_is_close_to_identity():
    calibrator = fit_platt_calibration(_well_calibrated_bets())
    for p in (0.2, 0.5, 0.8):
        assert calibrator.calibrate(p) == pytest.approx(p, abs=0.06)


def test_platt_on_overconfident_data_pulls_high_probabilities_down():
    calibrator = fit_platt_calibration(_overconfident_bets())
    # True relationship (true_rate = 0.6 * p) isn't itself logistic-in-logit,
    # so Platt only approximates it — check direction and rough magnitude,
    # not an exact match (isotonic, tested below, can match it much more closely).
    calibrated = calibrator.calibrate(0.95)
    assert calibrated < 0.85
    assert calibrated > 0.3


def test_platt_calibration_improves_brier_on_held_out_overconfident_data():
    train = _overconfident_bets(seed=10)
    holdout = _overconfident_bets(seed=11)
    calibrator = fit_platt_calibration(train)

    raw_brier = brier_score(holdout)
    calibrated_holdout = [
        BetRecord(probability=calibrator.calibrate(b.probability), bookmaker_odds=b.bookmaker_odds, won=b.won)
        for b in holdout
    ]
    calibrated_brier = brier_score(calibrated_holdout)
    assert calibrated_brier < raw_brier


def test_isotonic_is_monotonic_non_decreasing():
    calibrator = fit_isotonic_calibration(_overconfident_bets())
    ys = calibrator.ys
    assert all(ys[i] <= ys[i + 1] for i in range(len(ys) - 1))


def test_isotonic_on_overconfident_data_pulls_high_probabilities_down():
    calibrator = fit_isotonic_calibration(_overconfident_bets())
    assert calibrator.calibrate(0.95) < 0.95


def test_isotonic_improves_brier_on_held_out_overconfident_data():
    train = _overconfident_bets(seed=20)
    holdout = _overconfident_bets(seed=21)
    calibrator = fit_isotonic_calibration(train)

    raw_brier = brier_score(holdout)
    calibrated_holdout = [
        BetRecord(probability=calibrator.calibrate(b.probability), bookmaker_odds=b.bookmaker_odds, won=b.won)
        for b in holdout
    ]
    calibrated_brier = brier_score(calibrated_holdout)
    assert calibrated_brier < raw_brier


def test_isotonic_handles_duplicate_probabilities():
    bets = [BetRecord(probability=0.5, bookmaker_odds=2.0, won=w) for w in (True, False, True, False, True)]
    calibrator = fit_isotonic_calibration(bets)
    assert calibrator.xs == (0.5,)
    assert calibrator.calibrate(0.5) == pytest.approx(0.6)  # 3/5 won


def test_isotonic_clips_outside_observed_range():
    bets = [BetRecord(probability=p, bookmaker_odds=1.5, won=(p > 0.5)) for p in (0.3, 0.4, 0.5, 0.6, 0.7)]
    calibrator = fit_isotonic_calibration(bets)
    assert calibrator.calibrate(0.01) == calibrator.ys[0]
    assert calibrator.calibrate(0.99) == calibrator.ys[-1]


def test_calibrators_do_not_crash_on_single_bet():
    single = [BetRecord(probability=0.6, bookmaker_odds=1.8, won=True)]
    platt = fit_platt_calibration(single)
    isotonic = fit_isotonic_calibration(single)
    assert 0.0 <= platt.calibrate(0.6) <= 1.0
    assert 0.0 <= isotonic.calibrate(0.6) <= 1.0


def test_log_loss_also_improves_with_platt_on_overconfident_data():
    train = _overconfident_bets(seed=30)
    holdout = _overconfident_bets(seed=31)
    calibrator = fit_platt_calibration(train)

    raw_ll = log_loss(holdout)
    calibrated_holdout = [
        BetRecord(probability=calibrator.calibrate(b.probability), bookmaker_odds=b.bookmaker_odds, won=b.won)
        for b in holdout
    ]
    assert log_loss(calibrated_holdout) < raw_ll
