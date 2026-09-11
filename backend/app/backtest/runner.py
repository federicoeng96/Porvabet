"""Walk-forward backtest runner for the Dixon-Coles statistical engine.

No-leakage guarantee: for every match evaluated, the model is fit using ONLY
matches whose kickoff strictly precedes the current evaluation batch's earliest
kickoff (see `_batches_by_matchday_window`). Refitting once per batch (instead of
once per match) is a deliberate compute/precision trade-off — refitting on every
single match is O(n^2) optimizer calls and was not necessary for the ranking
questions this backtest answers (per-risk-level, per-market performance); the
trade-off itself needs no separate exemption from the no-leakage rule, because
matches inside the same batch never see each other's data, only prior batches'.

Risk-level bucketing here uses a deliberately simplified `RiskFactors` config
(see BACKTEST_SPEC.md "Backtest risk factor approximations"): `data_quality=1.0`
and `prediction_stability=1.0` and `lineup_dependency=0.0` because these signals
either don't vary in a pure historical-odds backtest or aren't recoverable
after the fact; `uncertainty` is derived from the training-sample size at fit
time, and `model_reliability` is a rolling out-of-sample calibration score
computed only from predictions already resolved earlier in the walk-forward
loop (never from the current or future match), which is itself leak-free.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from app.backtest.metrics import BetRecord, brier_score
from app.engine.decision.risk_score import RiskFactors
from app.engine.decision.selection import Candidate, build_risk_ladder
from app.engine.statistical.dixon_coles import DixonColesModel, GoalMatchInput
from app.providers.base.dto import HistoricalMatchRecord

MIN_TRAINING_MATCHES = 80
REFIT_BATCH_DAYS = 7
# Prefer true closing lines (see football_data_co_uk/provider.py) over
# pre-closing quotes: the closing line is the standard, more efficient
# benchmark for backtesting (closest the market gets to "correct" before
# kickoff). Pinnacle is preferred among bookmakers for its historically low
# margins/sharp pricing; Market Average as the next-best broad consensus.
BOOKMAKER_PREFERENCE = [
    "Pinnacle (closing)",
    "Market Average (closing)",
    "Bet365 (closing)",
    "Pinnacle",
    "Market Average",
    "Bet365",
]


@dataclass(frozen=True)
class ResolvedPrediction:
    match_date: date
    home_team: str
    away_team: str
    market_category: str
    outcome_code: str
    probability: float
    bookmaker_odds: float
    won: bool
    risk_level: int
    is_home_selection: bool


def _to_goal_input(m: HistoricalMatchRecord) -> GoalMatchInput:
    return GoalMatchInput(
        home_team=m.home_team_name,
        away_team=m.away_team_name,
        home_goals=m.home_goals_ft,
        away_goals=m.away_goals_ft,
        match_date=m.kickoff_utc.date(),
    )


def _pick_odds(odds_by_bookmaker: dict[str, dict[str, float]]) -> dict[str, float] | None:
    if not odds_by_bookmaker:
        return None
    for name in BOOKMAKER_PREFERENCE:
        if name in odds_by_bookmaker:
            return odds_by_bookmaker[name]
    return next(iter(odds_by_bookmaker.values()))


def _batches_by_window(
    matches: list[HistoricalMatchRecord], window_days: int
) -> list[list[HistoricalMatchRecord]]:
    matches = sorted(matches, key=lambda m: m.kickoff_utc)
    if not matches:
        return []
    batches: list[list[HistoricalMatchRecord]] = []
    current: list[HistoricalMatchRecord] = [matches[0]]
    window_start = matches[0].kickoff_utc.date()
    for m in matches[1:]:
        if (m.kickoff_utc.date() - window_start).days >= window_days:
            batches.append(current)
            current = [m]
            window_start = m.kickoff_utc.date()
        else:
            current.append(m)
    batches.append(current)
    return batches


def run_walk_forward_backtest(
    matches: list[HistoricalMatchRecord],
    min_training_matches: int = MIN_TRAINING_MATCHES,
    refit_batch_days: int = REFIT_BATCH_DAYS,
    total_goals_line: float = 2.5,
) -> list[ResolvedPrediction]:
    all_sorted = sorted(matches, key=lambda m: m.kickoff_utc)
    batches = _batches_by_window(all_sorted, refit_batch_days)

    resolved: list[ResolvedPrediction] = []
    reliability_history: list[BetRecord] = []  # only ever appended AFTER resolving a match
    training_pool: list[HistoricalMatchRecord] = []

    for batch in batches:
        if len(training_pool) < min_training_matches:
            training_pool.extend(batch)
            continue

        model = DixonColesModel()
        goal_inputs = [_to_goal_input(m) for m in training_pool]
        as_of = batch[0].kickoff_utc.date() - timedelta(days=1)
        model.fit(goal_inputs, as_of=as_of)

        train_n = len(training_pool)
        uncertainty = max(0.0, 1.0 - min(train_n, 300) / 300)
        reliability = 1.0 - min(brier_score(reliability_history) or 0.25, 1.0) if reliability_history else 0.5

        for m in batch:
            if m.home_team_name not in model.params.teams or m.away_team_name not in model.params.teams:
                continue  # newly promoted / unseen team this batch — skip rather than guess

            candidates = _build_candidates(model, m, uncertainty, reliability, total_goals_line)
            if not candidates:
                continue
            ladder = build_risk_ladder(candidates)

            for level_selection in ladder:
                sc = level_selection.main
                won = _outcome_won(sc.candidate, m, total_goals_line)
                pred = ResolvedPrediction(
                    match_date=m.kickoff_utc.date(),
                    home_team=m.home_team_name,
                    away_team=m.away_team_name,
                    market_category=sc.candidate.market_category,
                    outcome_code=sc.candidate.outcome_label,
                    probability=sc.candidate.probability,
                    bookmaker_odds=sc.candidate.bookmaker_odds,
                    won=won,
                    risk_level=level_selection.risk_level,
                    is_home_selection=sc.candidate.outcome_label == "HOME",
                )
                resolved.append(pred)

            # Update rolling reliability using only the MATCH_RESULT main candidate,
            # once per match (not once per risk level), to avoid inflating the
            # reliability sample with 10 correlated copies of the same match.
            match_result_candidate = next(
                (c for c in candidates if c.market_category == "MATCH_RESULT"), candidates[0]
            )
            reliability_history.append(
                BetRecord(
                    probability=match_result_candidate.probability,
                    bookmaker_odds=match_result_candidate.bookmaker_odds,
                    won=_outcome_won(match_result_candidate, m, total_goals_line),
                )
            )

        training_pool.extend(batch)

    return resolved


def _build_candidates(
    model: DixonColesModel,
    m: HistoricalMatchRecord,
    uncertainty: float,
    reliability: float,
    total_goals_line: float,
) -> list[Candidate]:
    candidates: list[Candidate] = []

    result_odds = _pick_odds(m.closing_odds_1x2)
    if result_odds:
        probs = model.match_result_probabilities(m.home_team_name, m.away_team_name)
        for code, label in (("H", "HOME"), ("D", "DRAW"), ("A", "AWAY")):
            if code not in result_odds:
                continue
            p = probs[label]
            factors = RiskFactors(
                probability=p,
                bookmaker_odds=result_odds[code],
                uncertainty=uncertainty,
                data_quality=1.0,
                model_reliability=reliability,
                prediction_stability=1.0,
                lineup_dependency=0.0,
            )
            candidates.append(
                Candidate(
                    market_outcome_key=f"MATCH_RESULT:{label}",
                    market_category="MATCH_RESULT",
                    market_label="1X2",
                    outcome_label=label,
                    probability=p,
                    bookmaker_odds=result_odds[code],
                    fair_odds_value=1.0 / p,
                    risk_factors=factors,
                )
            )

    ou_odds = _pick_odds(m.closing_odds_over_under_2_5)
    if ou_odds:
        probs = model.total_goals_probabilities(m.home_team_name, m.away_team_name, line=total_goals_line)
        for code, label in (("OVER", "OVER"), ("UNDER", "UNDER")):
            if code not in ou_odds:
                continue
            p = probs[label]
            factors = RiskFactors(
                probability=p,
                bookmaker_odds=ou_odds[code],
                uncertainty=uncertainty,
                data_quality=1.0,
                model_reliability=reliability,
                prediction_stability=1.0,
                lineup_dependency=0.0,
            )
            candidates.append(
                Candidate(
                    market_outcome_key=f"TOTAL_GOALS:{label}",
                    market_category="TOTAL_GOALS",
                    market_label=f"Over/Under {total_goals_line}",
                    outcome_label=label,
                    probability=p,
                    bookmaker_odds=ou_odds[code],
                    fair_odds_value=1.0 / p,
                    risk_factors=factors,
                )
            )

    return candidates


def _outcome_won(candidate: Candidate, m: HistoricalMatchRecord, total_goals_line: float) -> bool:
    if candidate.market_category == "MATCH_RESULT":
        actual = "HOME" if m.home_goals_ft > m.away_goals_ft else ("AWAY" if m.away_goals_ft > m.home_goals_ft else "DRAW")
        return candidate.outcome_label == actual
    if candidate.market_category == "TOTAL_GOALS":
        total = m.home_goals_ft + m.away_goals_ft
        if candidate.outcome_label == "OVER":
            return total > total_goals_line
        return total < total_goals_line
    raise ValueError(f"Unhandled market category {candidate.market_category!r}")
