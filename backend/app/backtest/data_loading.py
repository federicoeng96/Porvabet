"""Loads real historical match data (matches + closing odds) from the dev DB
into the DTOs `app.backtest.runner` expects.

Shared between `scripts/persist_backtest_results.py` and
`scripts/calibrate_risk_weights.py` (previously duplicated only in the
former) — kept here rather than in either script because a plain script
cannot import from another script (`python scripts/foo.py` puts the
script's own directory, not the project root, on `sys.path`), and because
this is genuinely reusable data-loading logic rather than one-off CLI glue.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Competition, Season
from app.models.market import Market, MarketOutcome, OddsQuote
from app.models.match import Match
from app.providers.base.dto import HistoricalMatchRecord


def load_season_matches(
    db: Session, competition_code: str, season_labels: set[str] | None = None
) -> list[Match]:
    """`season_labels=None` (the default) means every ingested season for
    this competition — `Match.home_goals_ft.is_not(None)` below already
    restricts to played matches, which in this project's real ingested data
    is equivalent to "every season currently in `ALL_SEASONS`"
    (`scripts/persist_backtest_results.py`) without needing that allowlist
    duplicated here. Pass `season_labels` explicitly to reproduce a prior
    run's exact season set instead of "whatever is in the DB today"."""
    comp = db.scalar(select(Competition).where(Competition.code == competition_code))
    seasons = db.scalars(select(Season).where(Season.competition_id == comp.id)).all()
    if season_labels is not None:
        seasons = [s for s in seasons if s.label in season_labels]
    season_ids = [s.id for s in seasons]
    return list(
        db.scalars(select(Match).where(Match.season_id.in_(season_ids), Match.home_goals_ft.is_not(None))).all()
    )


def load_goal_records(db: Session, competition_code: str, matches: list[Match]) -> list[HistoricalMatchRecord]:
    records = []
    for m in matches:
        market_rows = db.scalars(select(Market).where(Market.match_id == m.id)).all()
        odds_1x2: dict[str, dict[str, float]] = {}
        odds_ou: dict[str, dict[str, float]] = {}
        for market in market_rows:
            cat = market.category.value if hasattr(market.category, "value") else market.category
            outcomes = db.scalars(select(MarketOutcome).where(MarketOutcome.market_id == market.id)).all()
            for outcome in outcomes:
                quotes = db.scalars(select(OddsQuote).where(OddsQuote.market_outcome_id == outcome.id)).all()
                for q in quotes:
                    if cat == "MATCH_RESULT":
                        code_map = {"HOME": "H", "DRAW": "D", "AWAY": "A"}
                        odds_1x2.setdefault(q.bookmaker, {})[code_map[outcome.code]] = q.decimal_odds
                    elif cat == "TOTAL_GOALS":
                        odds_ou.setdefault(q.bookmaker, {})[outcome.code] = q.decimal_odds
        records.append(
            HistoricalMatchRecord(
                competition_code=competition_code,
                season_label="multi",
                kickoff_utc=m.kickoff_utc,
                home_team_name=m.home_team.name,
                away_team_name=m.away_team.name,
                home_goals_ft=m.home_goals_ft,
                away_goals_ft=m.away_goals_ft,
                home_goals_ht=m.home_goals_ht,
                away_goals_ht=m.away_goals_ht,
                closing_odds_1x2=odds_1x2,
                closing_odds_over_under_2_5=odds_ou,
            )
        )
    return records
