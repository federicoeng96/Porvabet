"""DB-backed tests for the analysis orchestration layer, using a small SYNTHETIC
round-robin of fictional teams (not real fixtures)."""

import random
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.engine.decision.analysis_runner import (
    MIN_TRAINING_MATCHES,
    InsufficientDataError,
    run_analysis_for_match,
)
from app.ingestion.match_ingestion import ingest_historical_match
from app.models.prediction import AnalysisVersion, RiskSelection
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
