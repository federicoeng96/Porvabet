"""DB-backed tests against the local Postgres test database (porvabet_test).
Every match/team here is fictional (SYNTHETIC), used only to verify the
ingestion mapping logic — not real data."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.ingestion.match_ingestion import (
    canonicalize_team_name,
    get_or_create_team,
    ingest_historical_match,
    resolve_understat_team_name,
)
from app.models.market import Market, MarketOutcome, OddsQuote
from app.models.match import Match
from app.models.stats import TeamMatchStats
from app.providers.base.dto import HistoricalMatchRecord


def _sample_record(external_ref="synthetic:test:1") -> HistoricalMatchRecord:
    return HistoricalMatchRecord(
        competition_code="EPL",
        season_label="2024/2025",
        kickoff_utc=datetime(2024, 9, 1, 15, 0, tzinfo=UTC),
        home_team_name="Synthetic United",
        away_team_name="Synthetic City",
        home_goals_ft=2,
        away_goals_ft=1,
        home_goals_ht=1,
        away_goals_ht=0,
        home_shots=14,
        away_shots=9,
        home_shots_on_target=6,
        away_shots_on_target=3,
        home_corners=7,
        away_corners=4,
        home_fouls=10,
        away_fouls=12,
        home_yellow_cards=2,
        away_yellow_cards=3,
        home_red_cards=0,
        away_red_cards=1,
        closing_odds_1x2={"Bet365": {"H": 1.9, "D": 3.6, "A": 4.2}},
        closing_odds_over_under_2_5={"Bet365": {"OVER": 1.85, "UNDER": 1.95}},
        external_ref=external_ref,
    )


def test_canonicalize_team_name_is_stable_and_normalized():
    assert canonicalize_team_name("Manchester United") == canonicalize_team_name("Manchester United")
    assert canonicalize_team_name("Bologna F.C.") == "bologna_f_c"


def test_resolve_understat_team_name_uses_alias_map(db_session):
    # football-data.co.uk (already ingested) spells it "Man United"; understat
    # says "Manchester United" — real mismatch found this session.
    existing = get_or_create_team(db_session, "Man United")
    db_session.flush()

    resolved = resolve_understat_team_name(db_session, "Manchester United")
    assert resolved is not None
    assert resolved.id == existing.id


def test_resolve_understat_team_name_matches_exact_spelling_without_alias(db_session):
    existing = get_or_create_team(db_session, "Arsenal")
    db_session.flush()

    resolved = resolve_understat_team_name(db_session, "Arsenal")
    assert resolved is not None
    assert resolved.id == existing.id


def test_resolve_understat_team_name_returns_none_when_team_not_ingested(db_session):
    # No "Team" row exists for this name at all — must not guess/create one.
    resolved = resolve_understat_team_name(db_session, "Some Unknown FC")
    assert resolved is None


def test_ingest_creates_teams_match_markets_and_odds(db_session):
    match = ingest_historical_match(db_session, _sample_record())
    db_session.flush()

    assert match.home_team.name == "Synthetic United"
    assert match.away_team.name == "Synthetic City"
    assert match.home_goals_ft == 2
    assert match.away_goals_ft == 1

    markets = db_session.scalars(select(Market).where(Market.match_id == match.id)).all()
    categories = {m.category.value if hasattr(m.category, "value") else m.category for m in markets}
    assert categories == {"MATCH_RESULT", "TOTAL_GOALS"}

    result_market = next(m for m in markets if m.label == "1X2")
    outcomes = db_session.scalars(
        select(MarketOutcome).where(MarketOutcome.market_id == result_market.id)
    ).all()
    assert {o.code for o in outcomes} == {"HOME", "DRAW", "AWAY"}

    home_outcome = next(o for o in outcomes if o.code == "HOME")
    odds = db_session.scalars(
        select(OddsQuote).where(OddsQuote.market_outcome_id == home_outcome.id)
    ).all()
    assert len(odds) == 1
    assert odds[0].decimal_odds == 1.9
    assert odds[0].bookmaker == "Bet365"


def test_ingest_persists_corners_cards_fouls_per_team(db_session):
    """Regression test: these fields were parsed by the provider but silently
    discarded during ingestion until this was fixed — see ROADMAP.md."""
    match = ingest_historical_match(db_session, _sample_record(external_ref="synthetic:test:stats"))
    db_session.flush()

    stats = db_session.scalars(
        select(TeamMatchStats).where(TeamMatchStats.match_id == match.id)
    ).all()
    assert len(stats) == 2

    home_stats = next(s for s in stats if s.is_home)
    away_stats = next(s for s in stats if not s.is_home)

    assert home_stats.team_id == match.home_team_id
    assert home_stats.shots == 14
    assert home_stats.shots_on_target == 6
    assert home_stats.corners == 7
    assert home_stats.fouls_committed == 10
    assert home_stats.yellow_cards == 2
    assert home_stats.red_cards == 0

    assert away_stats.team_id == match.away_team_id
    assert away_stats.corners == 4
    assert away_stats.fouls_committed == 12
    assert away_stats.yellow_cards == 3
    assert away_stats.red_cards == 1


def test_ingest_is_idempotent(db_session):
    record = _sample_record(external_ref="synthetic:test:idempotent")
    match1 = ingest_historical_match(db_session, record)
    db_session.flush()
    match2 = ingest_historical_match(db_session, record)
    db_session.flush()

    assert match1.id == match2.id
    all_matches = db_session.scalars(
        select(Match).where(Match.external_ref == "synthetic:test:idempotent")
    ).all()
    assert len(all_matches) == 1

    # Odds should be updated in place, not duplicated, on re-ingestion.
    markets = db_session.scalars(select(Market).where(Market.match_id == match1.id)).all()
    result_market = next(m for m in markets if m.label == "1X2")
    home_outcome = db_session.scalar(
        select(MarketOutcome).where(
            MarketOutcome.market_id == result_market.id, MarketOutcome.code == "HOME"
        )
    )
    odds = db_session.scalars(
        select(OddsQuote).where(OddsQuote.market_outcome_id == home_outcome.id)
    ).all()
    assert len(odds) == 1

    # TeamMatchStats should also be updated in place, not duplicated.
    stats = db_session.scalars(
        select(TeamMatchStats).where(TeamMatchStats.match_id == match1.id)
    ).all()
    assert len(stats) == 2
