"""Tests the count-market (corners/cards) backtest runner on SYNTHETIC data."""

import random
from datetime import date, timedelta

from app.backtest.count_market_runner import run_count_market_backtest, to_bet_records
from app.backtest.metrics import brier_score, hit_rate, profit_units, roi
from app.engine.statistical.count_market_model import CountMatchInput


def _synthetic_matches(seed: int = 3, n: int = 200) -> list[CountMatchInput]:
    rng = random.Random(seed)
    teams = [f"Team{i}" for i in range(6)]
    rate = {t: rng.uniform(3.0, 8.0) for t in teams}
    start = date(2022, 8, 1)
    matches = []
    for i in range(n):
        home, away = rng.sample(teams, 2)
        home_count = max(0, int(rng.gauss(rate[home] * 1.1, 2)))
        away_count = max(0, int(rng.gauss(rate[away] * 0.9, 2)))
        matches.append(CountMatchInput(home, away, home_count, away_count, start + timedelta(days=i)))
    return matches


def test_backtest_produces_resolved_predictions():
    matches = _synthetic_matches()
    resolved = run_count_market_backtest(matches, line=9.5)
    assert len(resolved) > 0
    assert all(r.outcome_code in ("OVER", "UNDER") for r in resolved)


def test_bet_records_have_no_bookmaker_odds():
    matches = _synthetic_matches()
    resolved = run_count_market_backtest(matches, line=9.5)
    bets = to_bet_records(resolved)
    assert all(b.bookmaker_odds is None for b in bets)


def test_roi_and_profit_are_none_without_odds():
    matches = _synthetic_matches()
    resolved = run_count_market_backtest(matches, line=9.5)
    bets = to_bet_records(resolved)
    assert roi(bets) is None
    assert profit_units(bets) is None


def test_hit_rate_and_brier_are_computable_without_odds():
    matches = _synthetic_matches()
    resolved = run_count_market_backtest(matches, line=9.5)
    bets = to_bet_records(resolved)
    assert 0.0 <= hit_rate(bets) <= 1.0
    assert brier_score(bets) >= 0.0


def test_no_leakage_respects_min_training_matches():
    matches = _synthetic_matches(n=30)  # fewer than MIN_TRAINING_MATCHES=40
    resolved = run_count_market_backtest(matches, line=9.5)
    assert resolved == []
