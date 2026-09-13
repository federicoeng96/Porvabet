"""Tests for app.engine.decision.count_market_estimates._load_count_training_matches.

Guards against a real N+1 query regression found during this session's
performance audit: the original implementation issued one `TeamMatchStats`
query per prior match inside a Python loop (~3800 individual round-trips
measured against the real dev DB's full historical dataset) instead of one
batched query — see CHANGELOG.md.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import event

from app.engine.decision.count_market_estimates import (
    MIN_TRAINING_MATCHES,
    _corners_extractor,
    _load_count_training_matches,
    compute_count_market_estimates,
)
from app.engine.statistical.count_market_model import PoissonCountModel
from app.ingestion.match_ingestion import ingest_historical_match
from app.providers.base.dto import HistoricalMatchRecord

TEAMS = ["Count Load A", "Count Load B", "Count Load C", "Count Load D"]


def _seed(db_session, n_matches: int):
    start = datetime(2024, 8, 1, 15, 0, tzinfo=UTC)
    matches = []
    for i in range(n_matches):
        home, away = TEAMS[i % 2], TEAMS[2 + (i % 2)]
        record = HistoricalMatchRecord(
            competition_code="EPL",
            season_label="2024/2025",
            kickoff_utc=start + timedelta(days=i),
            home_team_name=home,
            away_team_name=away,
            home_goals_ft=1,
            away_goals_ft=1,
            home_goals_ht=None,
            away_goals_ht=None,
            home_corners=5 + i,
            away_corners=3 + i,
            home_yellow_cards=1,
            away_yellow_cards=2,
            home_fouls=11,
            away_fouls=13,
            external_ref=f"count-load-synth:{i}",
        )
        matches.append(ingest_historical_match(db_session, record))
    db_session.commit()
    return matches


def _target_match(db_session, matches):
    from app.ingestion.match_ingestion import get_or_create_team
    from app.models.core import Season
    from app.models.enums import MatchStatus
    from app.models.match import Match

    last_kickoff = matches[-1].kickoff_utc
    season = db_session.get(Season, matches[-1].season_id)
    home = get_or_create_team(db_session, TEAMS[0])
    away = get_or_create_team(db_session, TEAMS[1])
    target = Match(
        season_id=season.id,
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_utc=last_kickoff + timedelta(days=7),
        status=MatchStatus.SCHEDULED,
        external_ref="count-load-synth:target",
    )
    db_session.add(target)
    db_session.flush()
    return target


def test_load_count_training_matches_returns_correct_values(db_session):
    matches = _seed(db_session, n_matches=6)
    target = _target_match(db_session, matches)

    results = _load_count_training_matches(db_session, target, _corners_extractor)

    assert len(results) == 6
    # Spot-check one: home_count/away_count come from the seeded home/away corners.
    by_date = {r.match_date: r for r in results}
    first_date = matches[0].kickoff_utc.date()
    assert by_date[first_date].home_count == 5
    assert by_date[first_date].away_count == 3


def test_load_count_training_matches_uses_a_bounded_number_of_queries(db_session):
    """Regression guard for the N+1 fix: the query count must stay flat
    (O(1), not O(n)) as the number of prior matches grows."""
    engine = db_session.get_bind()

    def count_queries(n_matches: int) -> int:
        matches = _seed(db_session, n_matches=n_matches)
        target = _target_match(db_session, matches)

        query_count = 0

        def _count(*args, **kwargs):
            nonlocal query_count
            query_count += 1

        event.listen(engine, "before_cursor_execute", _count)
        try:
            _load_count_training_matches(db_session, target, _corners_extractor)
        finally:
            event.remove(engine, "before_cursor_execute", _count)
        return query_count

    queries_for_6 = count_queries(6)
    queries_for_24 = count_queries(24)

    # Before the fix this was ~1 query per prior match (linear growth); after
    # the fix it's a small constant number regardless of how many prior
    # matches exist (one for the season, one for prior matches, one batched
    # stats query) — assert it does NOT scale with match count.
    assert queries_for_24 <= queries_for_6 + 2


def test_compute_count_market_estimates_reuses_the_fit_across_a_shared_kickoff(db_session, monkeypatch):
    """Same performance-audit finding as analysis_runner's model_fit_cache
    tests, for the count-market (CORNERS/CARDS/FOULS) fit specifically: two
    matches sharing the exact same (competition, kickoff) must fit each
    category's PoissonCountModel only once between them, not twice."""
    from app.ingestion.match_ingestion import get_or_create_team
    from app.models.core import Season
    from app.models.enums import MatchStatus
    from app.models.match import Match

    matches = _seed(db_session, n_matches=MIN_TRAINING_MATCHES + 5)
    last_kickoff = matches[-1].kickoff_utc
    shared_kickoff = last_kickoff + timedelta(days=7)
    season = db_session.get(Season, matches[-1].season_id)
    home = get_or_create_team(db_session, TEAMS[0])
    away = get_or_create_team(db_session, TEAMS[1])
    target_1 = Match(
        season_id=season.id, home_team_id=home.id, away_team_id=away.id,
        kickoff_utc=shared_kickoff, status=MatchStatus.SCHEDULED,
        external_ref="count-load-synth:shared:1",
    )
    target_2 = Match(
        season_id=season.id, home_team_id=home.id, away_team_id=away.id,
        kickoff_utc=shared_kickoff, status=MatchStatus.SCHEDULED,
        external_ref="count-load-synth:shared:2",
    )
    db_session.add_all([target_1, target_2])
    db_session.flush()

    fit_calls = 0
    original_fit = PoissonCountModel.fit

    def counting_fit(self, *args, **kwargs):
        nonlocal fit_calls
        fit_calls += 1
        return original_fit(self, *args, **kwargs)

    monkeypatch.setattr(PoissonCountModel, "fit", counting_fit)

    cache: dict = {}
    estimates_1 = compute_count_market_estimates(db_session, target_1, model_fit_cache=cache)
    estimates_2 = compute_count_market_estimates(db_session, target_2, model_fit_cache=cache)

    # 3 categories (CORNERS, CARDS, FOULS) fitted once each — not 6 (once per match).
    assert fit_calls == 3
    assert {e.market_category for e in estimates_1} == {"CORNERS", "CARDS", "FOULS"}
    assert {e.market_category for e in estimates_2} == {"CORNERS", "CARDS", "FOULS"}
