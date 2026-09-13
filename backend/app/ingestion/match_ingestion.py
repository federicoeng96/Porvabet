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

from app.models.core import Competition, Season, Source, Team
from app.models.enums import DataSourceCategory, MarketCategory, MatchStatus
from app.models.market import Market, MarketOutcome, OddsQuote
from app.models.match import Match
from app.models.stats import TeamMatchStats
from app.providers.base.dto import HistoricalMatchRecord, OddsQuoteRecord, UpcomingFixtureRecord

# outcome_code -> (market category, market label, outcome label) for the live
# markets an OddsProvider (e.g. BetfairExchangeOddsProvider) can return today —
# see `ingest_live_odds_quotes` below. CORNERS/CARDS are deliberately absent:
# no live odds source in this project covers them yet (see DATA_SOURCES.md),
# so a record with an unrecognized outcome_code is skipped, never guessed at.
LIVE_ODDS_OUTCOME_META: dict[str, tuple[MarketCategory, str, str]] = {
    "HOME": (MarketCategory.MATCH_RESULT, "1X2", "Home win"),
    "DRAW": (MarketCategory.MATCH_RESULT, "1X2", "Draw"),
    "AWAY": (MarketCategory.MATCH_RESULT, "1X2", "Away win"),
    "OVER": (MarketCategory.TOTAL_GOALS, "Over/Under 2.5 goals", "Over 2.5"),
    "UNDER": (MarketCategory.TOTAL_GOALS, "Over/Under 2.5 goals", "Under 2.5"),
}

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


# Hand-verified against real data (this session, 2023/24 EPL+Serie A team
# lists from both sources, extended when the 2015/16-2024/25 backfill hit
# promoted/relegated clubs not in the original 2023/24-only check) —
# understat.com's full/official club name mapped to the spelling
# football-data.co.uk uses (already ingested into `Team`). Deliberately
# explicit and small rather than fuzzy-matched: these are objective facts
# (the same club), not estimates, and the finite number of top-flight clubs
# makes a hand-curated map both accurate and easy to extend when a newly
# promoted/relegated club introduces another mismatch (fails loud via
# `resolve_understat_team_name` below, rather than guessing).
UNDERSTAT_TEAM_NAME_ALIASES: dict[str, str] = {
    "Manchester City": "Man City",
    "Manchester United": "Man United",
    "Newcastle United": "Newcastle",
    "Nottingham Forest": "Nott'm Forest",
    "Wolverhampton Wanderers": "Wolves",
    "AC Milan": "Milan",
    "West Bromwich Albion": "West Brom",
    "SPAL 2013": "Spal",
    "Parma Calcio 1913": "Parma",
}


def resolve_understat_team_name(db: Session, understat_name: str) -> Team | None:
    """Resolves an understat.com team title to an existing `Team` row already
    ingested from football-data.co.uk, via `UNDERSTAT_TEAM_NAME_ALIASES` when
    the spelling differs. Returns None (never guesses/creates a new Team) when
    no existing row matches — the caller must skip and report that team name
    rather than silently drop or fabricate rows for it."""
    candidate = UNDERSTAT_TEAM_NAME_ALIASES.get(understat_name, understat_name)
    return db.scalar(select(Team).where(Team.canonical_key == canonicalize_team_name(candidate)))


# Hand-verified against real data (this session): football-data.org's fixture
# API uses each club's full registered name ("Manchester United FC", "FC
# Internazionale Milano"), while football-data.co.uk — this project's primary,
# already-ingested source — uses short common names ("Man United", "Inter").
# Same pattern and same reasoning as UNDERSTAT_TEAM_NAME_ALIASES above (hand-
# curated, not fuzzy-matched): confirmed live by ingesting a real next-matchday
# fixture set and finding every non-newly-promoted club created a duplicate
# `Team` row instead of reusing the existing one (e.g. "Manchester United FC"
# id 71 next to the pre-existing "Man United" id 9) — see CHANGELOG.md/
# VERIFICATION_LOG.md for the concrete before/after. Extend this map, the same
# way UNDERSTAT_TEAM_NAME_ALIASES already gets extended, whenever a newly
# promoted/relegated club or a fixture from a season not yet seen introduces
# another mismatch.
FOOTBALL_DATA_ORG_TEAM_NAME_ALIASES: dict[str, str] = {
    "Manchester United FC": "Man United",
    "Manchester City FC": "Man City",
    "Brighton & Hove Albion FC": "Brighton",
    "Leeds United FC": "Leeds",
    "Newcastle United FC": "Newcastle",
    "Nottingham Forest FC": "Nott'm Forest",
    "Wolverhampton Wanderers FC": "Wolves",
    "West Bromwich Albion FC": "West Brom",
    "US Lecce": "Lecce",
    "AC Monza": "Monza",
    "SSC Napoli": "Napoli",
    "Bologna FC 1909": "Bologna",
    "US Sassuolo Calcio": "Sassuolo",
    "Juventus FC": "Juventus",
    "Como 1907": "Como",
    "Parma Calcio 1913": "Parma",
    "Torino FC": "Torino",
    "AS Roma": "Roma",
    "FC Internazionale Milano": "Inter",
    "Udinese Calcio": "Udinese",
    "AC Milan": "Milan",
}


def get_or_create_team(db: Session, name: str) -> Team:
    key = canonicalize_team_name(name)
    team = db.scalar(select(Team).where(Team.canonical_key == key))
    if team is None:
        team = Team(name=name, canonical_key=key)
        db.add(team)
        db.flush()
    return team


def resolve_or_create_team(db: Session, name: str, aliases: dict[str, str]) -> Team:
    """Like `get_or_create_team`, but tries `aliases` first so a name from a
    second provider (e.g. football-data.org) reuses the existing `Team` row
    for a club already known under a different spelling, rather than creating
    a silent duplicate. Falls back to `get_or_create_team` on the raw name
    when there is no alias entry or the aliased name has no existing match —
    which is the correct outcome for a genuinely new club (e.g. freshly
    promoted, never seen in previously-ingested data), not an error."""
    candidate = aliases.get(name)
    if candidate is not None:
        team = db.scalar(select(Team).where(Team.canonical_key == canonicalize_team_name(candidate)))
        if team is not None:
            return team
    return get_or_create_team(db, name)


def get_or_create_source(
    db: Session, key: str, name: str, category: DataSourceCategory, is_implemented: bool
) -> Source:
    source = db.scalar(select(Source).where(Source.key == key))
    if source is None:
        source = Source(key=key, name=name, category=category, is_implemented=is_implemented)
        db.add(source)
        db.flush()
    return source


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
    match.status = MatchStatus.FINISHED

    _ingest_1x2_odds(db, match, record.closing_odds_1x2)
    _ingest_ou25_odds(db, match, record.closing_odds_over_under_2_5)
    _ingest_team_stats(db, match, home_team, record, is_home=True)
    _ingest_team_stats(db, match, away_team, record, is_home=False)

    return match


def ingest_upcoming_fixture(db: Session, record: UpcomingFixtureRecord) -> Match:
    """Persists a not-yet-played fixture (e.g. from
    `FootballDataOrgFixtureProvider.get_next_matchday_fixtures`) as a
    `MatchStatus.SCHEDULED` `Match` row — no goals, no odds, no stats (none
    exist yet for a match that hasn't been played). Idempotent on
    `external_ref`, same pattern as `ingest_historical_match`: re-running this
    for the same fixture (e.g. a kickoff-time correction before the match is
    played) updates the existing row rather than creating a duplicate. Never
    overwrites a match that has since finished — see the guard below."""
    competition = get_or_create_competition(db, record.competition_code)
    season = get_or_create_season(db, competition, record.season_label)
    # football-data.org names differ from football-data.co.uk's (this
    # project's primary source, already ingested) — resolve via
    # FOOTBALL_DATA_ORG_TEAM_NAME_ALIASES to avoid a duplicate Team row for a
    # club that already exists, same pattern as understat's team names above.
    home_team = resolve_or_create_team(db, record.home_team_name, FOOTBALL_DATA_ORG_TEAM_NAME_ALIASES)
    away_team = resolve_or_create_team(db, record.away_team_name, FOOTBALL_DATA_ORG_TEAM_NAME_ALIASES)

    match = db.scalar(select(Match).where(Match.external_ref == record.external_ref))
    if match is None:
        match = Match(
            season_id=season.id,
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            kickoff_utc=record.kickoff_utc,
            status=MatchStatus.SCHEDULED,
            external_ref=record.external_ref,
        )
        db.add(match)
        db.flush()
        return match

    if match.status == MatchStatus.FINISHED:
        # A later re-run of this ingestion (e.g. a stale next-matchday fetch)
        # must never revert a since-completed match back to SCHEDULED or
        # touch its real result — historical ingestion is the only path
        # allowed to set FINISHED/goals for this external_ref.
        return match

    match.kickoff_utc = record.kickoff_utc
    return match


def _ingest_team_stats(
    db: Session, match: Match, team: Team, record: HistoricalMatchRecord, is_home: bool
) -> None:
    """Persists the per-team observed match stats (shots, corners, fouls, cards)
    that the provider already parses from football-data.co.uk but that were
    previously discarded here — see ARCHITECTURE.md/ROADMAP.md for context.
    These are the raw ingredients for corner/card markets; the statistical
    engine reads them via `app.engine.statistical.corners_cards`, never via
    this ingestion module directly."""
    existing = db.scalar(
        select(TeamMatchStats).where(
            TeamMatchStats.match_id == match.id, TeamMatchStats.team_id == team.id
        )
    )
    values = {
        "shots": record.home_shots if is_home else record.away_shots,
        "shots_on_target": record.home_shots_on_target if is_home else record.away_shots_on_target,
        "corners": record.home_corners if is_home else record.away_corners,
        "fouls_committed": record.home_fouls if is_home else record.away_fouls,
        "yellow_cards": record.home_yellow_cards if is_home else record.away_yellow_cards,
        "red_cards": record.home_red_cards if is_home else record.away_red_cards,
    }
    if existing is not None:
        for field, value in values.items():
            setattr(existing, field, value)
        return
    db.add(TeamMatchStats(match_id=match.id, team_id=team.id, is_home=is_home, **values))


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


def ingest_live_odds_quotes(
    db: Session, match: Match, records: list[OddsQuoteRecord], source: Source | None = None
) -> int:
    """Persists `OddsQuoteRecord`s from a live `OddsProvider` (e.g.
    `BetfairExchangeOddsProvider`) as new `OddsQuote` rows, creating the
    `Market`/`MarketOutcome` rows on demand — needed for a genuinely future
    fixture that has no historical closing-odds rows yet.

    Unlike `_upsert_closing_odds` (one closing price per bookmaker, updated in
    place), this always inserts a fresh row: a live quote is a point-in-time
    observation, and `_build_candidates_and_predictions` already picks the
    most recent `OddsQuote` per outcome, so preserving history here costs
    nothing and keeps a full price trail. A record whose `outcome_code` isn't
    in `LIVE_ODDS_OUTCOME_META` (e.g. a market this ingestion layer doesn't
    yet know how to place, such as corners/cards if a provider ever returns
    them) is skipped, never guessed at — see the module-level constant.

    Returns the number of `OddsQuote` rows written (0 when the provider had
    nothing available — never fabricated, per the project's standing rule).
    """
    written = 0
    for record in records:
        meta = LIVE_ODDS_OUTCOME_META.get(record.outcome_code)
        if meta is None:
            continue
        category, market_label, outcome_label = meta
        market = _get_or_create_market(db, match, category, market_label)
        if category == MarketCategory.TOTAL_GOALS:
            market.line = 2.5
        outcome = _get_or_create_outcome(db, market, record.outcome_code, outcome_label)
        db.add(
            OddsQuote(
                market_outcome_id=outcome.id,
                bookmaker=record.bookmaker,
                decimal_odds=record.decimal_odds,
                captured_at=record.captured_at,
                is_closing=record.is_closing,
                source_id=source.id if source else None,
            )
        )
        written += 1
    return written
