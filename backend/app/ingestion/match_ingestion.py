"""Maps provider DTOs onto the database schema (idempotent upserts).

This is the only place that translates a `HistoricalMatchRecord` (or other
provider DTO) into ORM rows — providers themselves never touch SQLAlchemy, and
the statistical/decision engines never touch a provider directly (see
ARCHITECTURE.md). Re-running ingestion for the same source data must not create
duplicate rows, which is why every entity is looked up by a stable natural key
(`canonical_key` for teams, `external_ref` for matches) before being created.
"""

import re
import unicodedata
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Competition, Season, Team
from app.models.enums import MarketCategory
from app.models.market import Market, MarketOutcome, OddsQuote
from app.models.match import Match
from app.providers.base.dto import HistoricalMatchRecord

COMPETITION_META = {
    "EPL": {"name": "Premier League", "country": "England"},
    "SERIE_A": {"name": "Serie A", "country": "Italy"},
}


def canonicalize_team_name(name: str) -> str:
    """Best-effort natural key so the same club matches across providers with
    slightly different spellings/abbreviations (e.g. "Man United" vs
    "Manchester United"). This is a lightweight normalization, not a full
    cross-provider entity-resolution system — see ROADMAP.md for a dedicated
    team-alias table if/when a second sports-data source is wired into
    ingestion alongside football-data.co.uk."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return text


def get_or_create_team(db: Session, name: str) -> Team:
    key = canonicalize_team_name(name)
    team = db.scalar(select(Team).where(Team.canonical_key == key))
    if team is None:
        team = Team(name=name, canonical_key=key)
        db.add(team)
        db.flush()
    return team


def get_or_create_competition(db: Session, code: str) -> Competition:
    competition = db.scalar(select(Competition).where(Competition.code == code))
    if competition is None:
        meta = COMPETITION_META.get(code, {"name": code, "country": "Unknown"})
        competition = Competition(code=code, name=meta["name"], country=meta["country"])
        db.add(competition)
        db.flush()
    return competition


def get_or_create_season(db: Session, competition: Competition, season_label: str) -> Season:
    season = db.scalar(
        select(Season).where(Season.competition_id == competition.id, Season.label == season_label)
    )
    if season is None:
        start_year = int(season_label.split("/")[0])
        season = Season(
            competition_id=competition.id,
            label=season_label,
            start_date=date(start_year, 7, 1),
            end_date=date(start_year + 1, 6, 30),
        )
        db.add(season)
        db.flush()
    return season


def ingest_historical_match(db: Session, record: HistoricalMatchRecord) -> Match:
    competition = get_or_create_competition(db, record.competition_code)
    season = get_or_create_season(db, competition, record.season_label)
    home_team = get_or_create_team(db, record.home_team_name)
    away_team = get_or_create_team(db, record.away_team_name)

    match = db.scalar(select(Match).where(Match.external_ref == record.external_ref))
    if match is None:
        match = Match(
            season_id=season.id,
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            kickoff_utc=record.kickoff_utc,
            external_ref=record.external_ref,
        )
        db.add(match)
        db.flush()

    match.home_goals_ft = record.home_goals_ft
    match.away_goals_ft = record.away_goals_ft
    match.home_goals_ht = record.home_goals_ht
    match.away_goals_ht = record.away_goals_ht
    from app.models.enums import MatchStatus

    match.status = MatchStatus.FINISHED

    _ingest_1x2_odds(db, match, record.closing_odds_1x2)
    _ingest_ou25_odds(db, match, record.closing_odds_over_under_2_5)

    return match


def _get_or_create_market(db: Session, match: Match, category: MarketCategory, label: str) -> Market:
    market = db.scalar(
        select(Market).where(Market.match_id == match.id, Market.category == category)
    )
    if market is None:
        market = Market(match_id=match.id, category=category, label=label)
        db.add(market)
        db.flush()
    return market


def _get_or_create_outcome(db: Session, market: Market, code: str, label: str) -> MarketOutcome:
    outcome = db.scalar(
        select(MarketOutcome).where(MarketOutcome.market_id == market.id, MarketOutcome.code == code)
    )
    if outcome is None:
        outcome = MarketOutcome(market_id=market.id, code=code, label=label)
        db.add(outcome)
        db.flush()
    return outcome


def _ingest_1x2_odds(db: Session, match: Match, odds_by_bookmaker: dict[str, dict[str, float]]) -> None:
    if not odds_by_bookmaker:
        return
    market = _get_or_create_market(db, match, MarketCategory.MATCH_RESULT, "1X2")
    outcomes = {
        "HOME": _get_or_create_outcome(db, market, "HOME", "Home win"),
        "DRAW": _get_or_create_outcome(db, market, "DRAW", "Draw"),
        "AWAY": _get_or_create_outcome(db, market, "AWAY", "Away win"),
    }
    code_map = {"H": "HOME", "D": "DRAW", "A": "AWAY"}
    for bookmaker, prices in odds_by_bookmaker.items():
        for raw_code, decimal_odds in prices.items():
            outcome = outcomes[code_map[raw_code]]
            _upsert_closing_odds(db, outcome, bookmaker, decimal_odds, match.kickoff_utc)


def _ingest_ou25_odds(db: Session, match: Match, odds_by_bookmaker: dict[str, dict[str, float]]) -> None:
    if not odds_by_bookmaker:
        return
    market = _get_or_create_market(db, match, MarketCategory.TOTAL_GOALS, "Over/Under 2.5 goals")
    market.line = 2.5
    outcomes = {
        "OVER": _get_or_create_outcome(db, market, "OVER", "Over 2.5"),
        "UNDER": _get_or_create_outcome(db, market, "UNDER", "Under 2.5"),
    }
    for bookmaker, prices in odds_by_bookmaker.items():
        for code, decimal_odds in prices.items():
            _upsert_closing_odds(db, outcomes[code], bookmaker, decimal_odds, match.kickoff_utc)


def _upsert_closing_odds(
    db: Session, outcome: MarketOutcome, bookmaker: str, decimal_odds: float, kickoff_utc
) -> None:
    existing = db.scalar(
        select(OddsQuote).where(
            OddsQuote.market_outcome_id == outcome.id,
            OddsQuote.bookmaker == bookmaker,
            OddsQuote.is_closing.is_(True),
        )
    )
    if existing is not None:
        existing.decimal_odds = decimal_odds
        return
    db.add(
        OddsQuote(
            market_outcome_id=outcome.id,
            bookmaker=bookmaker,
            decimal_odds=decimal_odds,
            captured_at=kickoff_utc - timedelta(hours=1),
            is_closing=True,
        )
    )
