"""Tests for the leak-free train/test split used to evaluate post-hoc
calibration on top of a walk-forward backtest — SYNTHETIC data only."""

import random

from app.backtest.calibration_runner import evaluate_calibration
from app.backtest.metrics import BetRecord


def _time_ordered_overconfident_bets(seed: int = 1, n_per_bin: int = 300) -> list[BetRecord]:
    """Simulates match_date ascending order implicitly via list order (as the
    walk-forward runners naturally produce): early matches use the SAME
    overconfident relationship as later ones here (stationary), so a
    calibrator fit on the first 80% should generalize to the last 20%."""
    rng = random.Random(seed)
    bets = []
    for _ in range(n_per_bin):
        for decile in range(10):
            p = decile / 10 + 0.05
            true_rate = p * 0.6
            bets.append(BetRecord(probability=p, bookmaker_odds=1.5, won=(rng.random() < true_rate)))
    return bets


def test_split_sizes_match_test_fraction():
    bets = _time_ordered_overconfident_bets(n_per_bin=100)
    result = evaluate_calibration(bets, test_fraction=0.2)
    assert result.n_train == int(len(bets) * 0.8)
    assert result.n_test == len(bets) - result.n_train


def test_calibration_fit_only_uses_train_portion():
    # First half well-calibrated, second half overconfident: a calibrator
    # fit only on the (well-calibrated) train portion should NOT correct the
    # overconfidence appearing only in the test portion — proves no leakage.
    rng = random.Random(7)
    calibrated_half = [BetRecord(probability=0.9, bookmaker_odds=1.1, won=(rng.random() < 0.9)) for _ in range(200)]
    overconfident_half = [BetRecord(probability=0.9, bookmaker_odds=1.1, won=(rng.random() < 0.5)) for _ in range(200)]
    bets = calibrated_half + overconfident_half

    result = evaluate_calibration(bets, test_fraction=0.5)
    # Calibrator trained on the well-calibrated half should leave p=0.9 ~ unchanged.
    assert result.platt.calibrate(0.9) > 0.8
    assert result.isotonic.calibrate(0.9) > 0.8


def test_both_calibrators_improve_brier_on_stationary_overconfident_data():
    bets = _time_ordered_overconfident_bets()
    result = evaluate_calibration(bets, test_fraction=0.2)
    assert result.raw_brier is not None
    assert result.platt_brier < result.raw_brier
    assert result.isotonic_brier < result.raw_brier


def test_result_preserves_test_set_size_in_calibration_curve():
    bets = _time_ordered_overconfident_bets(n_per_bin=100)
    result = evaluate_calibration(bets, test_fraction=0.2)
    total_in_curve = sum(b.count for b in result.raw_calibration_curve)
    assert total_in_curve == result.n_test
