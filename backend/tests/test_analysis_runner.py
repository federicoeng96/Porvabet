"""DB-backed tests for the analysis orchestration layer, using a small SYNTHETIC
round-robin of fictional teams (not real fixtures)."""

import random
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.backtest.metrics import BetRecord
from app.backtest.persistence import persist_backtest_run
from app.engine.decision.analysis_runner import (
    MIN_TRAINING_MATCHES,
    InsufficientDataError,
    run_analysis_for_match,
)
from app.ingestion.match_ingestion import get_or_create_competition, ingest_historical_match
from app.models.enums import MarketCategory, ModelFamily
from app.models.market import Market, MarketOutcome
from app.models.prediction import AnalysisVersion, Prediction, RiskSelection
from app.providers.base.dto import HistoricalMatchRecord

SYNTHETIC_TEAMS = ["Synth A", "Synth B", "Synth C", "Synth D"]


def _seed_matches(db_session, n_rounds: int) -> list:
    rng = random.Random(123)
    strength = {t: rng.uniform(0.7, 1.8) for t in SYNTHETIC_TEAMS}
    start = datetime(2024, 8, 1, 15, 0, tzinfo=UTC)
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
            record = HistoricalMatchRecord(
                competition_code="EPL",
                season_label="2024/2025",
                kickoff_utc=kickoff,
                home_team_name=home,
                away_team_name=away,
                home_goals_ft=home_goals,
                away_goals_ft=away_goals,
                home_goals_ht=None,
                away_goals_ht=None,
                closing_odds_1x2={"Market Average": {"H": 2.0, "D": 3.3, "A": 3.8}},
                closing_odds_over_under_2_5={"Market Average": {"OVER": 1.9, "UNDER": 1.9}},
                external_ref=f"synth:{round_i}:{home}:{away}",
            )
            matches.append(ingest_historical_match(db_session, record))
    db_session.flush()
    return matches


def test_run_analysis_raises_when_insufficient_history(db_session):
    matches = _seed_matches(db_session, n_rounds=3)  # only 6 matches, well under MIN_TRAINING_MATCHES
    with pytest.raises(InsufficientDataError):
        run_analysis_for_match(db_session, matches[-1].id)


def test_run_analysis_produces_full_ladder(db_session):
    n_rounds = (MIN_TRAINING_MATCHES // 2) + 6
    matches = _seed_matches(db_session, n_rounds=n_rounds)
    target = matches[-1]

    result = run_analysis_for_match(db_session, target.id)
    db_session.flush()

    assert len(result.risk_levels) == 10

    analysis_version = db_session.get(AnalysisVersion, result.analysis_version_id)
    assert analysis_version.is_current is True

    selections = db_session.scalars(
        select(RiskSelection).where(RiskSelection.analysis_version_id == analysis_version.id)
    ).all()
    levels_present = {s.risk_level for s in selections}
    assert levels_present == set(range(1, 11))

    mains = [s for s in selections if s.rank == 1]
    assert len(mains) == 10


def _well_calibrated_full_range_bets() -> list[BetRecord]:
    """40 bets per decile, each decile's win rate == its own predicted
    probability — perfectly calibrated everywhere, and every bin has
    n=40 >= reliability.MIN_BIN_COUNT, so whatever probability a real
    candidate lands on, it finds a trustworthy, well-calibrated bin."""
    bets = []
    for decile in range(10):
        p = decile / 10 + 0.05
        n_won = round(40 * p)
        for i in range(40):
            bets.append(BetRecord(probability=p, bookmaker_odds=1.5, won=(i < n_won)))
    return bets


def test_model_reliability_lowers_risk_once_a_real_backtest_is_persisted(db_session):
    """Before any Backtest row exists for this competition/market, reliability
    falls back to the conservative 0.0 (see reliability.py). Once a real,
    well-calibrated Backtest is persisted, the same candidate's risk score
    should go down — proof the wiring in analysis_runner.py actually reads
    it, not just a unit test of reliability.py in isolation."""
    n_rounds = (MIN_TRAINING_MATCHES // 2) + 6
    matches = _seed_matches(db_session, n_rounds=n_rounds)
    target = matches[-1]

    first = run_analysis_for_match(db_session, target.id)
    db_session.flush()
    first_home_risk = _match_result_home_risk_raw(db_session, first.analysis_version_id)
    assert first_home_risk is not None

    competition = get_or_create_competition(db_session, "EPL")
    db_session.flush()
    persist_backtest_run(
        db_session,
        bets=_well_calibrated_full_range_bets(),
        model_family=ModelFamily.DIXON_COLES_POISSON,
        market_category="MATCH_RESULT",
        competition_id=competition.id,
        version_label="test-reliability-wiring",
        window_start=date(2023, 8, 1),
        window_end=date(2024, 5, 1),
    )
    db_session.flush()

    second = run_analysis_for_match(db_session, target.id)
    db_session.flush()
    second_home_risk = _match_result_home_risk_raw(db_session, second.analysis_version_id)
    assert second_home_risk is not None

    assert second_home_risk < first_home_risk


def _match_result_home_risk_raw(db_session, analysis_version_id: int) -> float | None:
    row = db_session.execute(
        select(RiskSelection.risk_score_raw)
        .join(Prediction, RiskSelection.prediction_id == Prediction.id)
        .join(MarketOutcome, Prediction.market_outcome_id == MarketOutcome.id)
        .join(Market, MarketOutcome.market_id == Market.id)
        .where(
            RiskSelection.analysis_version_id == analysis_version_id,
            Market.category == MarketCategory.MATCH_RESULT,
            MarketOutcome.code == "HOME",
        )
        .limit(1)
    ).first()
    return row[0] if row else None


def test_rerunning_analysis_supersedes_previous_version(db_session):
    n_rounds = (MIN_TRAINING_MATCHES // 2) + 6
    matches = _seed_matches(db_session, n_rounds=n_rounds)
    target = matches[-1]

    first = run_analysis_for_match(db_session, target.id)
    db_session.flush()
    second = run_analysis_for_match(db_session, target.id)
    db_session.flush()

    assert first.analysis_version_id != second.analysis_version_id
    first_version = db_session.get(AnalysisVersion, first.analysis_version_id)
    second_version = db_session.get(AnalysisVersion, second.analysis_version_id)
    assert first_version.is_current is False
    assert second_version.is_current is True
