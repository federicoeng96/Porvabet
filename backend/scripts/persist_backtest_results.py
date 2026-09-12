"""Run the real walk-forward backtests (goals/1X2/O-U and corners/cards)
against ALL available real data and persist each segment as a `ModelVersion` +
`Backtest` row (ROADMAP.md item 1) — the source of truth `model_reliability`
in the live analysis endpoint reads from (see `app/engine/decision/reliability.py`),
replacing the previous fixed 0.5 placeholder.

Goals markets (MATCH_RESULT/TOTAL_GOALS): `run_walk_forward_backtest` at its
own default `refit_batch_days` (7 — see `app/backtest/runner.py`), over ALL 10
ingested seasons per competition. An earlier version of this script (see git
history) claimed `refit_batch_days=21` in this docstring while the code
actually used the module default (7) on only 6 seasons — a real labeling bug,
not a hidden change of numbers: the bug was in the prose here and in
BACKTEST_SPEC.md's comparison table, not in the persisted metrics themselves
(`ModelVersion.hyperparameters_json` always correctly recorded 7). Fixed by
widening to all 10 seasons, which is also exactly what ROADMAP.md item 2
concluded should replace the reduced 6-season approximation — so this run now
doubles as that item's production data, not just a bugfix.

Corners/cards: `run_count_market_backtest` with `PoissonCountModel` (the
model actually in production — see MODEL_SPEC.md / BACKTEST_SPEC.md "Poisson
vs binomiale negativa", NB was tested and not adopted) at `refit_batch_days=21`
(unchanged from the tested/decided protocol — only the negative-binomial
*comparison* used 6 seasons for time-budget reasons; the Poisson-only
production fit is fast enough to run on the full 10-season history), also
widened to all 10 seasons for the same reason as goals markets above.

Run against the dev DB already populated by `scripts/ingest_football_data.py`.
Re-running this script does not delete previous rows — it inserts a fresh
`ModelVersion`/`Backtest` pair with a new `run_at`; `reliability.py` always
reads the most recent one per (family, market_category, competition).
"""

from datetime import date

from sqlalchemy import select

from app.backtest.count_market_runner import run_count_market_backtest, to_bet_records
from app.backtest.metrics import BetRecord
from app.backtest.persistence import persist_backtest_run
from app.backtest.runner import REFIT_BATCH_DAYS, run_walk_forward_backtest
from app.db.session import SessionLocal
from app.engine.statistical.count_market_model import CountMatchInput, PoissonCountModel
from app.models.core import Competition, Season
from app.models.enums import ModelFamily
from app.models.market import Market, MarketOutcome, OddsQuote
from app.models.match import Match
from app.models.stats import TeamMatchStats
from app.providers.base.dto import HistoricalMatchRecord

ALL_SEASONS = {
    "2015/2016", "2016/2017", "2017/2018", "2018/2019", "2019/2020",
    "2020/2021", "2021/2022", "2022/2023", "2023/2024", "2024/2025",
}
VERSION_LABEL = "2026.09.12b-full-history"  # ModelVersion.version_label is varchar(32)


def _season_matches(db, competition_code: str) -> list[Match]:
    comp = db.scalar(select(Competition).where(Competition.code == competition_code))
    seasons = db.scalars(select(Season).where(Season.competition_id == comp.id)).all()
    season_ids = [s.id for s in seasons if s.label in ALL_SEASONS]
    return list(
        db.scalars(select(Match).where(Match.season_id.in_(season_ids), Match.home_goals_ft.is_not(None))).all()
    )


def _load_goal_records(db, competition_code: str, matches: list[Match]) -> list[HistoricalMatchRecord]:
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


def _load_count_records(db, matches: list[Match], extractor) -> list[CountMatchInput]:
    results = []
    for m in matches:
        stats = db.scalars(select(TeamMatchStats).where(TeamMatchStats.match_id == m.id)).all()
        if len(stats) != 2:
            continue
        home_stats = next((s for s in stats if s.is_home), None)
        away_stats = next((s for s in stats if not s.is_home), None)
        if home_stats is None or away_stats is None:
            continue
        home_val, away_val = extractor(home_stats), extractor(away_stats)
        if home_val is None or away_val is None:
            continue
        results.append(CountMatchInput(m.home_team.name, m.away_team.name, home_val, away_val, m.kickoff_utc.date()))
    return results


def _corners_extractor(s):
    return s.corners


def _cards_extractor(s):
    if s.yellow_cards is None and s.red_cards is None:
        return None
    return (s.yellow_cards or 0) + (s.red_cards or 0)


def _window(dates: list[date]) -> tuple[date, date]:
    return min(dates), max(dates)


def persist_goal_markets(db, competition_code: str) -> None:
    comp = db.scalar(select(Competition).where(Competition.code == competition_code))
    matches = _season_matches(db, competition_code)
    records = _load_goal_records(db, competition_code, matches)
    resolved = run_walk_forward_backtest(records, refit_batch_days=REFIT_BATCH_DAYS)
    if not resolved:
        print(f"{competition_code}: no resolved goal-market predictions, skipping")
        return

    hyperparameters = {"refit_batch_days": REFIT_BATCH_DAYS, "seasons": sorted(ALL_SEASONS)}
    leakage_note = (
        "Walk-forward: model refit only on matches strictly before each batch's "
        "earliest kickoff (see app/backtest/runner.py docstring)."
    )

    for market_category in ("MATCH_RESULT", "TOTAL_GOALS"):
        segment = [r for r in resolved if r.market_category == market_category]
        if not segment:
            continue
        bets = [
            BetRecord(r.probability, r.bookmaker_odds, r.won, r.risk_level, r.market_category, r.is_home_selection)
            for r in segment
        ]
        window_start, window_end = _window([r.match_date for r in segment])
        bt = persist_backtest_run(
            db,
            bets=bets,
            model_family=ModelFamily.DIXON_COLES_POISSON,
            market_category=market_category,
            competition_id=comp.id,
            version_label=VERSION_LABEL,
            window_start=window_start,
            window_end=window_end,
            hyperparameters=hyperparameters,
            notes="Real walk-forward backtest, see BACKTEST_SPEC.md.",
            leakage_check_notes=leakage_note,
        )
        print(
            f"{competition_code} {market_category}: n={bt.n_predictions} hit_rate={bt.hit_rate:.3f} "
            f"brier={bt.brier_score:.4f} log_loss={bt.log_loss:.4f} (backtest id={bt.id})"
        )


def persist_count_markets(db, competition_code: str) -> None:
    comp = db.scalar(select(Competition).where(Competition.code == competition_code))
    matches = _season_matches(db, competition_code)
    hyperparameters = {"refit_batch_days": 21, "seasons": sorted(ALL_SEASONS), "model": "PoissonCountModel"}
    leakage_note = (
        "Walk-forward: model refit only on matches strictly before each batch's "
        "earliest kickoff (see app/backtest/count_market_runner.py docstring). "
        "No real bookmaker price exists for these markets (see MODEL_SPEC.md) — "
        "roi/profit_units/yield_pct are correctly None, not a fabricated number."
    )

    for market_category, extractor, line in (("CORNERS", _corners_extractor, 9.5), ("CARDS", _cards_extractor, 3.5)):
        count_matches = _load_count_records(db, matches, extractor)
        resolved = run_count_market_backtest(count_matches, line=line, model_factory=PoissonCountModel)
        if not resolved:
            print(f"{competition_code} {market_category}: no resolved predictions, skipping")
            continue
        bets = to_bet_records(resolved)
        window_start, window_end = _window([r.match_date for r in resolved])
        bt = persist_backtest_run(
            db,
            bets=bets,
            model_family=ModelFamily.POISSON_COUNT_MODEL,
            market_category=market_category,
            competition_id=comp.id,
            version_label=VERSION_LABEL,
            window_start=window_start,
            window_end=window_end,
            hyperparameters=hyperparameters,
            notes="Real walk-forward backtest, see BACKTEST_SPEC.md. No bookmaker odds for this market.",
            leakage_check_notes=leakage_note,
        )
        print(
            f"{competition_code} {market_category}: n={bt.n_predictions} hit_rate={bt.hit_rate:.3f} "
            f"brier={bt.brier_score:.4f} log_loss={bt.log_loss:.4f} (backtest id={bt.id})"
        )


def main() -> None:
    db = SessionLocal()
    try:
        for competition_code in ("EPL", "SERIE_A"):
            persist_goal_markets(db, competition_code)
            persist_count_markets(db, competition_code)
        db.commit()
        print("\nCommitted all backtest rows.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
