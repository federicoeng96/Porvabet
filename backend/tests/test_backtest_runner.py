"""Tests for `run_walk_forward_backtest` — specifically that it actually
simulates the full 10-level risk-ladder precompute (not just per-market
metrics in isolation). This module had real production usage (the numbers
in BACKTEST_SPEC.md come from it) but no dedicated unit test before this —
a fast synthetic check here catches a regression before the next expensive
real-data run, rather than relying only on manual inspection of
BACKTEST_SPEC.md's published numbers.

Every team/match here is SYNTHETIC (fictional teams), used only to exercise
the walk-forward/risk-ladder wiring — never real data.
"""

import random
from datetime import UTC, datetime, timedelta

from app.backtest.metrics import segment
from app.backtest.runner import MIN_TRAINING_MATCHES, run_walk_forward_backtest
from app.providers.base.dto import HistoricalMatchRecord

SYNTHETIC_TEAMS = ["Synth A", "Synth B", "Synth C", "Synth D", "Synth E", "Synth F"]


def _synthetic_matches(n_rounds: int) -> list[HistoricalMatchRecord]:
    rng = random.Random(42)
    strength = {t: rng.uniform(0.7, 1.8) for t in SYNTHETIC_TEAMS}
    start = datetime(2020, 8, 1, 15, 0, tzinfo=UTC)
    matches = []
    for round_i in range(n_rounds):
        teams = SYNTHETIC_TEAMS[:]
        rng.shuffle(teams)
        for i in range(0, len(teams), 2):
            home, away = teams[i], teams[i + 1]
            lam, mu = strength[home] * 1.3, strength[away]
            home_goals = min(int(rng.gammavariate(max(lam, 0.1), 1)), 6)
            away_goals = min(int(rng.gammavariate(max(mu, 0.1), 1)), 6)
            kickoff = start + timedelta(days=7 * round_i)
            matches.append(
                HistoricalMatchRecord(
                    competition_code="EPL",
                    season_label="2020/2021",
                    kickoff_utc=kickoff,
                    home_team_name=home,
                    away_team_name=away,
                    home_goals_ft=home_goals,
                    away_goals_ft=away_goals,
                    home_goals_ht=None,
                    away_goals_ht=None,
                    closing_odds_1x2={"Market Average": {"H": 2.0, "D": 3.3, "A": 3.8}},
                    closing_odds_over_under_2_5={"Market Average": {"OVER": 1.9, "UNDER": 1.9}},
                    external_ref=f"synth-backtest:{round_i}:{home}:{away}",
                )
            )
    return matches


def test_run_walk_forward_backtest_produces_all_ten_risk_levels():
    # 3 matches/round x enough rounds to clear MIN_TRAINING_MATCHES with
    # plenty of evaluation matches left over.
    n_rounds = (MIN_TRAINING_MATCHES // 3) + 20
    matches = _synthetic_matches(n_rounds)

    resolved = run_walk_forward_backtest(matches)

    assert resolved  # something was actually resolved, not silently empty
    risk_levels_present = {r.risk_level for r in resolved}
    assert risk_levels_present == set(range(1, 11))


def test_run_walk_forward_backtest_risk_level_is_never_none():
    n_rounds = (MIN_TRAINING_MATCHES // 3) + 20
    matches = _synthetic_matches(n_rounds)

    resolved = run_walk_forward_backtest(matches)

    assert all(r.risk_level is not None for r in resolved)
    assert all(1 <= r.risk_level <= 10 for r in resolved)


def test_segment_by_risk_level_matches_backtest_spec_shape():
    """This is exactly the aggregation BACKTEST_SPEC.md's "per livello di
    rischio" table reports (hit rate/ROI per risk level 1-10) — confirms the
    resolved predictions carry everything `segment()` needs, end to end."""
    n_rounds = (MIN_TRAINING_MATCHES // 3) + 20
    matches = _synthetic_matches(n_rounds)
    resolved = run_walk_forward_backtest(matches)

    from app.backtest.metrics import BetRecord

    bets = [
        BetRecord(probability=r.probability, bookmaker_odds=r.bookmaker_odds, won=r.won, risk_level=r.risk_level)
        for r in resolved
    ]
    by_level = segment(bets, key=lambda b: b.risk_level)

    assert set(by_level) == {str(n) for n in range(1, 11)}
    for level_stats in by_level.values():
        assert level_stats["n"] > 0
        assert level_stats["hit_rate"] is not None
        assert level_stats["roi"] is not None


def test_run_walk_forward_backtest_returns_nothing_below_min_training():
    # Well under MIN_TRAINING_MATCHES — no batch should ever be evaluated.
    matches = _synthetic_matches(n_rounds=3)
    resolved = run_walk_forward_backtest(matches)
    assert resolved == []
