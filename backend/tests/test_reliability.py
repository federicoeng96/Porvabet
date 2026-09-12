"""Tests for real backtest-derived model_reliability (replaces the previous
0.5 placeholder — see ROADMAP.md / analysis_runner.py)."""

from datetime import date

import pytest

from app.backtest.metrics import BetRecord
from app.backtest.persistence import persist_backtest_run
from app.engine.decision.reliability import MIN_BIN_COUNT, model_reliability_for
from app.ingestion.match_ingestion import get_or_create_competition
from app.models.enums import ModelFamily


def _bets_with_calibration(n_low: int, n_high_good: int, n_high_bad: int) -> list[BetRecord]:
    """n_low bets around p=0.5 (well calibrated: ~50% win), n_high_good bets
    around p=0.85 that are ALSO well calibrated (~85% win), n_high_bad bets
    around p=0.85 that are overconfident (only ~50% win) — lets a test push
    a specific bin toward "reliable" or "unreliable" independently."""
    bets = []
    for i in range(n_low):
        bets.append(BetRecord(probability=0.55, bookmaker_odds=1.8, won=(i % 2 == 0)))
    n_good_won = round(n_high_good * 0.85)
    for i in range(n_high_good):
        bets.append(BetRecord(probability=0.85, bookmaker_odds=1.2, won=(i < n_good_won)))
    n_bad_won = round(n_high_bad * 0.50)
    for i in range(n_high_bad):
        bets.append(BetRecord(probability=0.85, bookmaker_odds=1.2, won=(i < n_bad_won)))
    return bets


def _persist(db_session, bets, competition_code="EPL", market_category="MATCH_RESULT", label="test"):
    competition = get_or_create_competition(db_session, competition_code)
    db_session.flush()
    return persist_backtest_run(
        db_session,
        bets=bets,
        model_family=ModelFamily.DIXON_COLES_POISSON,
        market_category=market_category,
        competition_id=competition.id,
        version_label=label,
        window_start=date(2023, 8, 1),
        window_end=date(2024, 5, 1),
    ), competition


def test_reliable_bin_gives_high_reliability(db_session):
    bets = _bets_with_calibration(n_low=0, n_high_good=MIN_BIN_COUNT + 10, n_high_bad=0)
    _, competition = _persist(db_session, bets)
    db_session.flush()

    estimate = model_reliability_for(
        db_session, ModelFamily.DIXON_COLES_POISSON, "MATCH_RESULT", competition.id, probability=0.85
    )
    assert estimate.value is not None
    assert estimate.value > 0.9  # well-calibrated bin: predicted ~0.85, observed ~0.85


def test_overconfident_bin_gives_low_reliability(db_session):
    bets = _bets_with_calibration(n_low=0, n_high_good=0, n_high_bad=MIN_BIN_COUNT + 10)
    _, competition = _persist(db_session, bets)
    db_session.flush()

    estimate = model_reliability_for(
        db_session, ModelFamily.DIXON_COLES_POISSON, "MATCH_RESULT", competition.id, probability=0.85
    )
    assert estimate.value is not None
    assert estimate.value < 0.7  # predicted ~0.85, observed ~0.50 -> gap ~0.35 -> reliability ~0.65


def test_sparse_bin_falls_back_to_segment_level(db_session):
    # The 0.85 bin has only a handful of observations (below MIN_BIN_COUNT),
    # but the segment overall (0.55 bin) has plenty — should fall back rather
    # than trust the sparse bin, and should not error.
    bets = _bets_with_calibration(n_low=MIN_BIN_COUNT + 50, n_high_good=5, n_high_bad=0)
    _, competition = _persist(db_session, bets)
    db_session.flush()

    estimate = model_reliability_for(
        db_session, ModelFamily.DIXON_COLES_POISSON, "MATCH_RESULT", competition.id, probability=0.85
    )
    assert estimate.value is not None
    assert "segment-level" in estimate.detail


def test_no_backtest_at_all_returns_not_estimable(db_session):
    competition = get_or_create_competition(db_session, "SERIE_A")
    db_session.flush()

    estimate = model_reliability_for(
        db_session, ModelFamily.DIXON_COLES_POISSON, "MATCH_RESULT", competition.id, probability=0.7
    )
    assert estimate.value is None
    assert "no persisted Backtest" in estimate.detail


def test_backtest_exists_but_every_bin_too_sparse_returns_not_estimable(db_session):
    # A handful of bets spread thinly across many bins: the segment has *some*
    # data everywhere but never enough in any single bin to trust.
    bets = [
        BetRecord(probability=p, bookmaker_odds=1.5, won=True)
        for p in (0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95)
    ]
    _, competition = _persist(db_session, bets)
    db_session.flush()

    estimate = model_reliability_for(
        db_session, ModelFamily.DIXON_COLES_POISSON, "MATCH_RESULT", competition.id, probability=0.85
    )
    assert estimate.value is None
    assert "not estimable" in estimate.detail


def test_uses_most_recent_backtest_when_several_exist(db_session):
    stale_bets = _bets_with_calibration(n_low=0, n_high_good=0, n_high_bad=MIN_BIN_COUNT + 10)
    _, competition = _persist(db_session, stale_bets, label="stale-run")
    db_session.flush()

    fresh_bets = _bets_with_calibration(n_low=0, n_high_good=MIN_BIN_COUNT + 10, n_high_bad=0)
    persist_backtest_run(
        db_session,
        bets=fresh_bets,
        model_family=ModelFamily.DIXON_COLES_POISSON,
        market_category="MATCH_RESULT",
        competition_id=competition.id,
        version_label="fresh-run",
        window_start=date(2024, 8, 1),
        window_end=date(2025, 5, 1),
    )
    db_session.flush()

    estimate = model_reliability_for(
        db_session, ModelFamily.DIXON_COLES_POISSON, "MATCH_RESULT", competition.id, probability=0.85
    )
    assert estimate.value is not None
    assert estimate.value > 0.9  # picked the fresh (well-calibrated), not the stale (overconfident) run


def test_wrong_market_category_is_not_estimable(db_session):
    bets = _bets_with_calibration(n_low=0, n_high_good=MIN_BIN_COUNT + 10, n_high_bad=0)
    _, competition = _persist(db_session, bets, market_category="MATCH_RESULT")
    db_session.flush()

    estimate = model_reliability_for(
        db_session, ModelFamily.DIXON_COLES_POISSON, "TOTAL_GOALS", competition.id, probability=0.85
    )
    assert estimate.value is None


@pytest.mark.parametrize("probability", [0.0, -0.1, 1.1])
def test_out_of_range_probability_still_returns_a_result_not_a_crash(db_session, probability):
    bets = _bets_with_calibration(n_low=MIN_BIN_COUNT + 10, n_high_good=0, n_high_bad=0)
    _, competition = _persist(db_session, bets)
    db_session.flush()

    estimate = model_reliability_for(
        db_session, ModelFamily.DIXON_COLES_POISSON, "MATCH_RESULT", competition.id, probability=probability
    )
    # No bin matches an out-of-[0,1) probability except the closed-at-1.0 case;
    # falls back to segment-level rather than raising.
    assert estimate.value is not None or "not estimable" in estimate.detail
