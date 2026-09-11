import pytest

from app.backtest.metrics import (
    BetRecord,
    brier_score,
    calibration_curve,
    hit_rate,
    log_loss,
    profit_units,
    roi,
    segment,
    yield_pct,
)


def _bets():
    return [
        BetRecord(probability=0.5, bookmaker_odds=2.0, won=True, risk_level=1),
        BetRecord(probability=0.5, bookmaker_odds=2.0, won=False, risk_level=1),
        BetRecord(probability=0.25, bookmaker_odds=4.0, won=True, risk_level=8),
        BetRecord(probability=0.25, bookmaker_odds=4.0, won=False, risk_level=8),
    ]


def test_hit_rate():
    assert hit_rate(_bets()) == pytest.approx(0.5)
    assert hit_rate([]) is None


def test_roi_breakeven_at_fair_odds():
    # Two bets at true 50% and fair odds 2.0, one wins one loses -> exactly breakeven.
    bets = _bets()[:2]
    assert roi(bets) == pytest.approx(0.0)


def test_yield_matches_roi_percent_under_flat_staking():
    bets = _bets()
    assert yield_pct(bets) == pytest.approx((roi(bets) or 0) * 100)


def test_profit_units():
    bets = [BetRecord(0.5, 2.0, True), BetRecord(0.5, 2.0, False)]
    assert profit_units(bets) == pytest.approx(0.0)  # +1 - 1


def test_brier_score_perfect_prediction_is_zero():
    perfect = [BetRecord(1.0, 2.0, True), BetRecord(0.0, 2.0, False)]
    assert brier_score(perfect) == pytest.approx(0.0)


def test_brier_score_worst_case_prediction_is_one():
    worst = [BetRecord(0.0, 2.0, True), BetRecord(1.0, 2.0, False)]
    assert brier_score(worst) == pytest.approx(1.0)


def test_log_loss_penalizes_confident_wrong_predictions_heavily():
    confident_right = [BetRecord(0.99, 2.0, True)]
    confident_wrong = [BetRecord(0.99, 2.0, False)]
    assert log_loss(confident_wrong) > log_loss(confident_right)


def test_calibration_curve_bins_and_counts():
    bets = _bets()
    curve = calibration_curve(bets, n_bins=4)
    assert len(curve) == 4
    assert sum(b.count for b in curve) == len(bets)


def test_segment_groups_by_key():
    bets = _bets()
    by_risk = segment(bets, lambda b: b.risk_level)
    assert set(by_risk.keys()) == {"1", "8"}
    assert by_risk["1"]["n"] == 2
    assert by_risk["8"]["n"] == 2
