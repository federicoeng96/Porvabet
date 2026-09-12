"""API-level tests for the batch analysis endpoint (ROADMAP.md item 10) —
SYNTHETIC teams, same fixture pattern as test_analysis_runner.py.

This is the first API-layer test in the project: uses FastAPI's TestClient
with `get_db` overridden to the same transactional `db_session` fixture every
other DB-backed test uses, so it rolls back like the rest and never touches
the dev database.
"""

import random
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.engine.decision.analysis_runner import MIN_TRAINING_MATCHES
from app.ingestion.match_ingestion import ingest_historical_match
from app.main import app
from app.providers.base.dto import HistoricalMatchRecord

SYNTHETIC_TEAMS = ["API A", "API B", "API C", "API D"]


@pytest.fixture(autouse=True)
def _reset_dependency_overrides():
    # `app` is a module-level singleton — dependency_overrides set by
    # `_client()` below must not leak `db_session` from one test's
    # transaction into the next test's.
    yield
    app.dependency_overrides.clear()


def _seed_matches(db_session, n_rounds: int) -> list:
    rng = random.Random(321)
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
                external_ref=f"api-synth:{round_i}:{home}:{away}",
            )
            matches.append(ingest_historical_match(db_session, record))
    # Commit (not just flush) the seed data: the batch endpoint itself calls
    # session.commit()/rollback() per match, and a mid-test rollback rolls
    # back to the most recent savepoint boundary — committing here first
    # establishes that boundary *after* the seed data, so a later rollback
    # inside the endpoint can never undo the fixture itself. The fixture's
    # own outer `transaction.rollback()` at teardown still discards all of
    # this (commit included) once the test ends.
    db_session.commit()
    return matches


def _client(db_session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_batch_analyze_all_matches_defaults_to_every_match(db_session):
    n_rounds = (MIN_TRAINING_MATCHES // 2) + 6
    matches = _seed_matches(db_session, n_rounds=n_rounds)
    client = _client(db_session)

    resp = client.post("/matches/analyze-batch", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == len(matches)
    assert body["succeeded"] + body["insufficient_data"] + body["failed"] == body["total"]
    assert body["succeeded"] > 0


def test_batch_analyze_specific_match_ids(db_session):
    n_rounds = (MIN_TRAINING_MATCHES // 2) + 6
    matches = _seed_matches(db_session, n_rounds=n_rounds)
    client = _client(db_session)
    target_ids = [matches[-1].id, matches[-2].id]

    resp = client.post("/matches/analyze-batch", json={"match_ids": target_ids})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    returned_ids = {item["match_id"] for item in body["results"]}
    assert returned_ids == set(target_ids)


def test_batch_analyze_reports_insufficient_data_without_failing_whole_batch(db_session):
    # Only 3 rounds seeded (6 matches) — well under MIN_TRAINING_MATCHES, so
    # every match should come back "insufficient_data", not abort/500.
    matches = _seed_matches(db_session, n_rounds=3)
    client = _client(db_session)

    resp = client.post("/matches/analyze-batch", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == len(matches)
    assert body["insufficient_data"] == len(matches)
    assert body["succeeded"] == 0
    assert all(item["status"] == "insufficient_data" for item in body["results"])


def test_batch_analyze_reports_error_for_unknown_match_id_without_failing_batch(db_session):
    n_rounds = (MIN_TRAINING_MATCHES // 2) + 6
    matches = _seed_matches(db_session, n_rounds=n_rounds)
    client = _client(db_session)
    bad_id = 999_999_999

    resp = client.post("/matches/analyze-batch", json={"match_ids": [matches[-1].id, bad_id]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["failed"] == 1
    assert body["succeeded"] == 1
    error_item = next(item for item in body["results"] if item["match_id"] == bad_id)
    assert error_item["status"] == "error"


def test_match_detail_exposes_nd_estimates_for_markets_without_a_quote(db_session):
    """API-level check that additional_estimates carries the generalized
    "n/d" shape (one row per outcome, MATCH_RESULT included, not just
    CORNERS/CARDS's OVER/UNDER pair). Sets up the analysis directly via
    run_analysis_for_match (never through the HTTP /analyze endpoint, which
    would default to the real Betfair provider chain and attempt a live
    network call this test suite must never make) — only the read path
    (`GET /matches/{id}`) goes through the actual FastAPI router/serialization.
    """
    from datetime import timedelta

    from app.engine.decision.analysis_runner import run_analysis_for_match
    from app.ingestion.match_ingestion import get_or_create_season, get_or_create_team
    from app.models.enums import MatchStatus
    from app.models.match import Match
    from app.providers.base.dto import OddsQuoteRecord

    n_rounds = (MIN_TRAINING_MATCHES // 2) + 6
    matches = _seed_matches(db_session, n_rounds=n_rounds)
    last_kickoff = matches[-1].kickoff_utc

    from app.ingestion.match_ingestion import get_or_create_competition

    competition = get_or_create_competition(db_session, "EPL")
    season = get_or_create_season(db_session, competition, "2024/2025")
    home = get_or_create_team(db_session, "API A")
    away = get_or_create_team(db_session, "API B")
    future_match = Match(
        season_id=season.id,
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_utc=last_kickoff + timedelta(days=7),
        status=MatchStatus.SCHEDULED,
        external_ref="api-synth:future:nd",
    )
    db_session.add(future_match)
    db_session.flush()

    class _FakeProvider:
        def is_available(self):
            return True

        def get_odds_for_match(self, home_team_name, away_team_name, kickoff_utc_iso):
            now = last_kickoff + timedelta(days=6)
            return [
                OddsQuoteRecord("Betfair", "1X2", "HOME", 2.0, now, is_closing=False),
                OddsQuoteRecord("Betfair", "1X2", "DRAW", 3.3, now, is_closing=False),
                OddsQuoteRecord("Betfair", "1X2", "AWAY", 3.8, now, is_closing=False),
            ]

    run_analysis_for_match(db_session, future_match.id, odds_provider=_FakeProvider())
    db_session.commit()

    client = _client(db_session)
    resp = client.get(f"/matches/{future_match.id}")
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["risk_levels"]) == 10  # MATCH_RESULT candidates fill the whole ladder

    nd = body["additional_estimates"]
    outcomes = {(e["market_category"], e["outcome_label"]) for e in nd}
    assert outcomes == {("TOTAL_GOALS", "OVER"), ("TOTAL_GOALS", "UNDER")}
    for estimate in nd:
        assert estimate["probability"] > 0
        assert estimate["fair_odds"] > 0
        assert estimate["note"]  # explains why Value/Alert are n/d
