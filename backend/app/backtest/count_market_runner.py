"""Walk-forward backtest for count-based markets (corners, cards).

Same no-leakage discipline as `app.backtest.runner` (refit only on strictly
prior batches), but deliberately does NOT report ROI/profit/yield: see
`app.engine.decision.count_market_estimates` for why there is no real
bookmaker price for these markets in any data source currently integrated —
`BetRecord.bookmaker_odds=None` here, and `app.backtest.metrics.roi`/
`profit_units` correctly return None rather than a fabricated number. What
IS reported — hit_rate, Brier score, log loss, calibration — needs only the
model's probability and the realized outcome, not a price, so it is exactly
as valid a check of "is this model any good" as for the priced markets.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from app.backtest.metrics import BetRecord
from app.engine.statistical.count_market_model import CountMatchInput, PoissonCountModel

MIN_TRAINING_MATCHES = 40
REFIT_BATCH_DAYS = 21  # same widened window used for the real goals backtest, for the same time-budget reason


@dataclass(frozen=True)
class ResolvedCountPrediction:
    match_date: date
    home_team: str
    away_team: str
    outcome_code: str  # "OVER" | "UNDER" — whichever the model favored
    probability: float
    won: bool


def run_count_market_backtest(
    matches: list[CountMatchInput],
    line: float,
    min_training_matches: int = MIN_TRAINING_MATCHES,
    refit_batch_days: int = REFIT_BATCH_DAYS,
) -> list[ResolvedCountPrediction]:
    all_sorted = sorted(matches, key=lambda m: m.match_date)
    batches = _batches_by_window(all_sorted, refit_batch_days)

    resolved: list[ResolvedCountPrediction] = []
    training_pool: list[CountMatchInput] = []

    for batch in batches:
        if len(training_pool) < min_training_matches:
            training_pool.extend(batch)
            continue

        model = PoissonCountModel()
        as_of = batch[0].match_date - timedelta(days=1)
        model.fit(training_pool, as_of=as_of)

        for m in batch:
            if m.home_team not in model.params.teams or m.away_team not in model.params.teams:
                continue  # unseen team this batch — skip rather than guess, same policy as the goals backtest

            probs = model.match_total_probabilities(m.home_team, m.away_team, line=line)
            actual_total = m.home_count + m.away_count
            actual_side = "OVER" if actual_total > line else "UNDER"
            # No odds to rank candidates by value here — evaluate whichever side
            # the model itself favors, mirroring "what would the model's own
            # single principal call have been".
            favored_side = "OVER" if probs["OVER"] >= probs["UNDER"] else "UNDER"
            resolved.append(
                ResolvedCountPrediction(
                    match_date=m.match_date,
                    home_team=m.home_team,
                    away_team=m.away_team,
                    outcome_code=favored_side,
                    probability=probs[favored_side],
                    won=(favored_side == actual_side),
                )
            )

        training_pool.extend(batch)

    return resolved


def to_bet_records(resolved: list[ResolvedCountPrediction]) -> list[BetRecord]:
    return [
        BetRecord(probability=r.probability, bookmaker_odds=None, won=r.won)
        for r in resolved
    ]


def _batches_by_window(
    matches: list[CountMatchInput], window_days: int
) -> list[list[CountMatchInput]]:
    matches = sorted(matches, key=lambda m: m.match_date)
    if not matches:
        return []
    batches: list[list[CountMatchInput]] = []
    current: list[CountMatchInput] = [matches[0]]
    window_start = matches[0].match_date
    for m in matches[1:]:
        if (m.match_date - window_start).days >= window_days:
            batches.append(current)
            current = [m]
            window_start = m.match_date
        else:
            current.append(m)
    batches.append(current)
    return batches
