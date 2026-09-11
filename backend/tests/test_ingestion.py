"""DB-backed tests against the local Postgres test database (porvabet_test).
Every match/team here is fictional (SYNTHETIC), used only to verify the
ingestion mapping logic — not real data."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.ingestion.match_ingestion import canonicalize_team_name, ingest_historical_match
from app.models.market import Market, MarketOutcome, OddsQuote
from app.models.match import Match
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
        closing_odds_1x2={"Bet365": {"H": 1.9, "D": 3.6, "A": 4.2}},
        closing_odds_over_under_2_5={"Bet365": {"OVER": 1.85, "UNDER": 1.95}},
        external_ref=external_ref,
    )


def test_canonicalize_team_name_is_stable_and_normalized():
    assert canonicalize_team_name("Manchester United") == canonicalize_team_name("Manchester United")
    assert canonicalize_team_name("Bologna F.C.") == "bologna_f_c"


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
