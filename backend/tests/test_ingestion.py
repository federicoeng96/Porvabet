"""DB-backed tests against the local Postgres test database (porvabet_test).
Every match/team here is fictional (SYNTHETIC), used only to verify the
ingestion mapping logic — not real data."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.ingestion.match_ingestion import (
    FOOTBALL_DATA_ORG_TEAM_NAME_ALIASES,
    canonicalize_team_name,
    get_or_create_competition,
    get_or_create_season,
    get_or_create_team,
    ingest_historical_match,
    ingest_live_odds_quotes,
    ingest_upcoming_fixture,
    resolve_or_create_team,
    resolve_understat_team_name,
)
from app.models.enums import MatchStatus
from app.models.market import Market, MarketOutcome, OddsQuote
from app.models.match import Match
from app.models.stats import TeamMatchStats
from app.providers.base.dto import HistoricalMatchRecord, OddsQuoteRecord, UpcomingFixtureRecord


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


def _scheduled_match_with_no_markets(db_session, external_ref: str) -> Match:
    """A genuinely future fixture as it exists before any odds have ever been
    ingested for it — no Market/MarketOutcome/OddsQuote rows at all, unlike
    every match `ingest_historical_match` touches (which always comes bundled
    with closing odds). This is exactly the case `ingest_live_odds_quotes`
    must handle: get-or-create everything from scratch."""
    competition = get_or_create_competition(db_session, "EPL")
    season = get_or_create_season(db_session, competition, "2026/2027")
    home = get_or_create_team(db_session, "Synthetic Rovers")
    away = get_or_create_team(db_session, "Synthetic Wanderers")
    match = Match(
        season_id=season.id,
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_utc=datetime(2026, 9, 20, 15, 0, tzinfo=UTC),
        status=MatchStatus.SCHEDULED,
        external_ref=external_ref,
    )
    db_session.add(match)
    db_session.flush()
    return match


def test_ingest_live_odds_quotes_creates_markets_for_future_fixture(db_session):
    match = _scheduled_match_with_no_markets(db_session, "synthetic:live:1")
    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    records = [
        OddsQuoteRecord("Betfair", "1X2", "HOME", 2.10, now, is_closing=False),
        OddsQuoteRecord("Betfair", "1X2", "DRAW", 3.40, now, is_closing=False),
        OddsQuoteRecord("Betfair", "1X2", "AWAY", 3.80, now, is_closing=False),
        OddsQuoteRecord("Betfair", "Over/Under 2.5", "OVER", 1.90, now, is_closing=False),
        OddsQuoteRecord("Betfair", "Over/Under 2.5", "UNDER", 1.95, now, is_closing=False),
    ]

    written = ingest_live_odds_quotes(db_session, match, records)
    db_session.flush()

    assert written == 5
    markets = db_session.scalars(select(Market).where(Market.match_id == match.id)).all()
    categories = {m.category.value if hasattr(m.category, "value") else m.category for m in markets}
    assert categories == {"MATCH_RESULT", "TOTAL_GOALS"}

    total_goals_market = next(m for m in markets if m.category.value == "TOTAL_GOALS")
    assert total_goals_market.line == 2.5

    result_market = next(m for m in markets if m.category.value == "MATCH_RESULT")
    home_outcome = db_session.scalar(
        select(MarketOutcome).where(
            MarketOutcome.market_id == result_market.id, MarketOutcome.code == "HOME"
        )
    )
    odds = db_session.scalars(
        select(OddsQuote).where(OddsQuote.market_outcome_id == home_outcome.id)
    ).all()
    assert len(odds) == 1
    assert odds[0].decimal_odds == 2.10
    assert odds[0].bookmaker == "Betfair"
    assert odds[0].is_closing is False


def test_ingest_live_odds_quotes_appends_history_rather_than_overwriting(db_session):
    match = _scheduled_match_with_no_markets(db_session, "synthetic:live:2")
    t1 = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 9, 19, 11, 0, tzinfo=UTC)

    ingest_live_odds_quotes(
        db_session, match, [OddsQuoteRecord("Betfair", "1X2", "HOME", 2.10, t1, is_closing=False)]
    )
    db_session.flush()
    ingest_live_odds_quotes(
        db_session, match, [OddsQuoteRecord("Betfair", "1X2", "HOME", 2.05, t2, is_closing=False)]
    )
    db_session.flush()

    home_outcome = db_session.scalar(
        select(MarketOutcome).where(MarketOutcome.code == "HOME")
    )
    odds = db_session.scalars(
        select(OddsQuote)
        .where(OddsQuote.market_outcome_id == home_outcome.id)
        .order_by(OddsQuote.captured_at)
    ).all()
    assert [o.decimal_odds for o in odds] == [2.10, 2.05]


def test_ingest_live_odds_quotes_skips_unrecognized_outcome_codes(db_session):
    """Never guesses a Market/MarketOutcome for a market this ingestion layer
    doesn't have a placement rule for (e.g. corners/cards) — see
    LIVE_ODDS_OUTCOME_META's docstring."""
    match = _scheduled_match_with_no_markets(db_session, "synthetic:live:3")
    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    records = [OddsQuoteRecord("Betfair", "Corners O/U", "OVER_9_5", 1.90, now, is_closing=False)]

    written = ingest_live_odds_quotes(db_session, match, records)
    db_session.flush()

    assert written == 0
    markets = db_session.scalars(select(Market).where(Market.match_id == match.id)).all()
    assert markets == []


def test_resolve_or_create_team_uses_alias_map_to_avoid_duplicate(db_session):
    # Real bug found this session: football-data.org returns "Manchester
    # United FC", football-data.co.uk (already ingested) has "Man United" —
    # without the alias, ingest_upcoming_fixture silently created a second,
    # duplicate Team row for the same club.
    existing = get_or_create_team(db_session, "Man United")
    db_session.flush()

    resolved = resolve_or_create_team(db_session, "Manchester United FC", FOOTBALL_DATA_ORG_TEAM_NAME_ALIASES)
    assert resolved.id == existing.id


def test_resolve_or_create_team_creates_new_team_for_genuinely_new_club(db_session):
    # A club with no alias entry and no pre-existing row (e.g. freshly
    # promoted, never seen in previously-ingested data) must still get a
    # real Team row, not be dropped or forced onto an unrelated match.
    resolved = resolve_or_create_team(db_session, "Coventry City FC", FOOTBALL_DATA_ORG_TEAM_NAME_ALIASES)
    db_session.flush()
    assert resolved.name == "Coventry City FC"


def test_ingest_upcoming_fixture_reuses_existing_team_via_football_data_org_alias(db_session):
    existing_home = get_or_create_team(db_session, "Man United")
    existing_away = get_or_create_team(db_session, "Man City")
    db_session.flush()

    record = UpcomingFixtureRecord(
        competition_code="EPL",
        season_label="2026/2027",
        kickoff_utc=datetime(2026, 9, 20, 14, 0, tzinfo=UTC),
        home_team_name="Manchester United FC",
        away_team_name="Manchester City FC",
        external_ref="football_data_org:900010",
    )

    match = ingest_upcoming_fixture(db_session, record)
    db_session.flush()

    assert match.home_team_id == existing_home.id
    assert match.away_team_id == existing_away.id


def test_ingest_upcoming_fixture_creates_scheduled_match(db_session):
    record = UpcomingFixtureRecord(
        competition_code="EPL",
        season_label="2026/2027",
        kickoff_utc=datetime(2026, 9, 20, 14, 0, tzinfo=UTC),
        home_team_name="Synthetic Arsenal",
        away_team_name="Synthetic Chelsea",
        external_ref="football_data_org:900001",
    )

    match = ingest_upcoming_fixture(db_session, record)
    db_session.flush()

    assert match.status == MatchStatus.SCHEDULED
    assert match.home_team.name == "Synthetic Arsenal"
    assert match.away_team.name == "Synthetic Chelsea"
    assert match.home_goals_ft is None
    assert match.away_goals_ft is None
    assert match.kickoff_utc == datetime(2026, 9, 20, 14, 0, tzinfo=UTC)


def test_ingest_upcoming_fixture_is_idempotent(db_session):
    record = UpcomingFixtureRecord(
        competition_code="EPL",
        season_label="2026/2027",
        kickoff_utc=datetime(2026, 9, 20, 14, 0, tzinfo=UTC),
        home_team_name="Synthetic Arsenal",
        away_team_name="Synthetic Chelsea",
        external_ref="football_data_org:900002",
    )

    match1 = ingest_upcoming_fixture(db_session, record)
    db_session.flush()
    # Re-fetched a day later with a corrected kickoff time (TV rescheduling).
    corrected = UpcomingFixtureRecord(
        competition_code="EPL",
        season_label="2026/2027",
        kickoff_utc=datetime(2026, 9, 21, 12, 30, tzinfo=UTC),
        home_team_name="Synthetic Arsenal",
        away_team_name="Synthetic Chelsea",
        external_ref="football_data_org:900002",
    )
    match2 = ingest_upcoming_fixture(db_session, corrected)
    db_session.flush()

    assert match1.id == match2.id
    all_matches = db_session.scalars(
        select(Match).where(Match.external_ref == "football_data_org:900002")
    ).all()
    assert len(all_matches) == 1
    assert match2.kickoff_utc == datetime(2026, 9, 21, 12, 30, tzinfo=UTC)


def test_ingest_upcoming_fixture_never_reverts_a_finished_match(db_session):
    """If a stale next-matchday fetch is re-run after the match has already
    been played and ingested as FINISHED (via ingest_historical_match), this
    must never revert its status or touch its real result."""
    historical = _sample_record(external_ref="football_data_org:already-finished")
    finished_match = ingest_historical_match(db_session, historical)
    db_session.flush()
    assert finished_match.status == MatchStatus.FINISHED

    stale_fixture = UpcomingFixtureRecord(
        competition_code="EPL",
        season_label="2024/2025",
        kickoff_utc=datetime(2099, 1, 1, tzinfo=UTC),  # obviously wrong if it were applied
        home_team_name="Synthetic United",
        away_team_name="Synthetic City",
        external_ref="football_data_org:already-finished",
    )
    result = ingest_upcoming_fixture(db_session, stale_fixture)
    db_session.flush()

    assert result.id == finished_match.id
    assert result.status == MatchStatus.FINISHED
    assert result.home_goals_ft == 2  # untouched
    assert result.kickoff_utc != datetime(2099, 1, 1, tzinfo=UTC)
