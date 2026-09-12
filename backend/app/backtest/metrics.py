"""Backtest metrics — see BACKTEST_SPEC.md for definitions and rationale.

All functions here are pure and take already-realized (probability, odds, outcome)
triples — they know nothing about how those were produced, so the same functions
serve the overall report and every per-segment breakdown (per risk level, per
market, home/away, per value bucket).
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BetRecord:
    probability: float  # model's probability for the selected outcome
    # None for markets with no real bookmaker price at all (e.g. corners/cards —
    # see count_market_estimates.py): such bets contribute to hit_rate/brier/
    # log_loss/calibration but are excluded from roi/profit_units/yield_pct,
    # which return None rather than a fabricated figure if every bet lacks odds.
    bookmaker_odds: float | None
    won: bool
    risk_level: int | None = None
    market_category: str | None = None
    is_home_selection: bool | None = None
    is_player_market: bool = False


def hit_rate(bets: list[BetRecord]) -> float | None:
    if not bets:
        return None
    return sum(1 for b in bets if b.won) / len(bets)


def roi(bets: list[BetRecord], stake: float = 1.0) -> float | None:
    """Flat-stake ROI: total profit / total staked. Bets with no real bookmaker
    price (bookmaker_odds=None) are excluded — returns None if none remain,
    rather than silently treating a missing price as zero profit."""
    priced = [b for b in bets if b.bookmaker_odds is not None]
    if not priced:
        return None
    total_staked = stake * len(priced)
    total_return = sum((b.bookmaker_odds * stake if b.won else 0.0) for b in priced)
    return (total_return - total_staked) / total_staked


def yield_pct(bets: list[BetRecord], stake: float = 1.0) -> float | None:
    """Equivalent to ROI*100 under flat staking; kept as a distinct named metric
    because BACKTEST_SPEC.md reports it separately (and a future variable-stake
    strategy, e.g. Kelly sizing, would make the two diverge)."""
    r = roi(bets, stake)
    return None if r is None else r * 100.0


def profit_units(bets: list[BetRecord], stake: float = 1.0) -> float | None:
    priced = [b for b in bets if b.bookmaker_odds is not None]
    if not priced:
        return None
    return sum((b.bookmaker_odds * stake - stake if b.won else -stake) for b in priced)


def brier_score(bets: list[BetRecord]) -> float | None:
    if not bets:
        return None
    return sum((b.probability - (1.0 if b.won else 0.0)) ** 2 for b in bets) / len(bets)


def log_loss(bets: list[BetRecord], eps: float = 1e-9) -> float | None:
    if not bets:
        return None
    total = 0.0
    for b in bets:
        p = min(max(b.probability, eps), 1 - eps)
        outcome = 1.0 if b.won else 0.0
        total -= outcome * math.log(p) + (1 - outcome) * math.log(1 - p)
    return total / len(bets)


@dataclass(frozen=True)
class CalibrationBin:
    bin_low: float
    bin_high: float
    predicted_mean: float | None
    observed_frequency: float | None
    count: int


def calibration_curve(bets: list[BetRecord], n_bins: int = 10) -> list[CalibrationBin]:
    edges = [i / n_bins for i in range(n_bins + 1)]
    bins: list[CalibrationBin] = []
    for i in range(n_bins):
        low, high = edges[i], edges[i + 1]
        in_bin = [b for b in bets if (low <= b.probability < high) or (i == n_bins - 1 and b.probability == high)]
        if not in_bin:
            bins.append(CalibrationBin(low, high, None, None, 0))
            continue
        predicted_mean = sum(b.probability for b in in_bin) / len(in_bin)
        observed = sum(1 for b in in_bin if b.won) / len(in_bin)
        bins.append(CalibrationBin(low, high, predicted_mean, observed, len(in_bin)))
    return bins


def segment(bets: list[BetRecord], key) -> dict:
    """Group bets by `key(bet) -> segment_label` and compute the core metric set
    per segment. Used for per-risk-level, per-market, home/away, per-value-bucket
    breakdowns from a single implementation."""
    groups: dict[str, list[BetRecord]] = {}
    for b in bets:
        groups.setdefault(str(key(b)), []).append(b)
    return {
        label: {
            "n": len(group),
            "hit_rate": hit_rate(group),
            "roi": roi(group),
            "yield_pct": yield_pct(group),
            "profit_units": profit_units(group),
            "brier_score": brier_score(group),
            "log_loss": log_loss(group),
        }
        for label, group in groups.items()
    }


def value_bucket_label(value: float) -> str:
    if value < -0.05:
        return "negative"
    if value < 0.0:
        return "slightly_negative"
    if value < 0.05:
        return "slightly_positive"
    if value < 0.15:
        return "positive"
    return "high"
