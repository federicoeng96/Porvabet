"""Risk scoring (1-10) for a single candidate selection.

Per the brief, risk must be "a dynamic combination of probability, odds, value,
data quality, uncertainty, model reliability, prediction stability, match context,
dependency on unofficial lineups — NOT an arbitrary probability threshold."

Design: each factor below is normalized to [0, 1] where 0 = contributes nothing
to risk and 1 = maximally risky, then combined as a weighted sum into a single
continuous `risk_raw` in [0, 1]. The weights are an explicit, documented starting
point (not derived from data yet) — MODEL_SPEC.md records them as provisional and
BACKTEST_SPEC.md's per-risk-level metrics are exactly what should be used to
recalibrate them (e.g. if Risk 3 selections don't actually outperform Risk 7 ones
on hit rate, the weights are wrong and should be refit, not the bucketing logic).

Turning the continuous `risk_raw` into a 1-10 level is done relative to the full
set of candidates available for a given match (see selection.py) — i.e. rank-based
bucketing, not a fixed absolute cutoff — so "risk 1" always means "the least risky
of everything we could offer for this match today", which is what lets the display
logic be a pure lookup with no recomputation when the user changes the slider.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskFactors:
    probability: float  # model probability of the outcome, (0, 1]
    bookmaker_odds: float | None  # decimal odds, > 1 — None when no real market price
    # exists for this outcome from any source (see Candidate.bookmaker_odds); the
    # odds_magnitude factor below is then never guessed, its weight is redistributed
    # across the other (known) factors instead — see compute_risk_raw.
    uncertainty: float  # 0..1, model's own uncertainty about `probability` (e.g. from posterior/CI width)
    data_quality: float  # 0..1, 1 = complete/reliable inputs, 0 = sparse/unreliable
    model_reliability: float  # 0..1, from the real backtest calibration curve for this
    # market/competition (see app/engine/decision/reliability.py) — 0.0 when there isn't
    # enough backtest evidence to estimate it with confidence (fail-conservative, not a guess)
    prediction_stability: float  # 0..1, 1 = probability unchanged vs previous analysis version
    lineup_dependency: float  # 0..1, 0 if not lineup-dependent, higher if it depends on an
    # unofficial/conflicting probable lineup


# Provisional weights (see module docstring) — must sum to 1.0.
WEIGHTS = {
    "improbability": 0.30,      # 1 - probability
    "odds_magnitude": 0.10,     # normalized log-odds, correlated with improbability but not identical
    "uncertainty": 0.20,
    "data_quality": 0.15,       # contributes as (1 - data_quality)
    "model_reliability": 0.10,  # contributes as (1 - model_reliability)
    "instability": 0.10,        # 1 - prediction_stability
    "lineup_dependency": 0.05,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def compute_risk_raw(factors: RiskFactors) -> float:
    improbability = 1.0 - factors.probability

    if factors.bookmaker_odds is None:
        # No real market price for this candidate anywhere (see
        # Candidate.bookmaker_odds/RiskFactors.bookmaker_odds) — never fabricate an
        # odds_magnitude value to fill this factor (e.g. from the model's own fair
        # odds, which would just double-count `improbability` under a different
        # name). Instead redistribute its weight proportionally across the factors
        # we can actually observe, same "never guess a number we don't have" rule
        # used everywhere else in this module/project.
        weights = {k: w for k, w in WEIGHTS.items() if k != "odds_magnitude"}
        remaining = sum(weights.values())
        weights = {k: w / remaining for k, w in weights.items()}
        odds_term = 0.0
    else:
        weights = WEIGHTS
        # log-odds normalized against a generous 1..15 decimal-odds range so typical
        # football markets span most of [0, 1] without long-odds outliers saturating it.
        odds_term = weights["odds_magnitude"] * _clip01(
            _log_scale(factors.bookmaker_odds, low=1.01, high=15.0)
        )

    score = (
        weights["improbability"] * improbability
        + odds_term
        + weights["uncertainty"] * _clip01(factors.uncertainty)
        + weights["data_quality"] * (1.0 - _clip01(factors.data_quality))
        + weights["model_reliability"] * (1.0 - _clip01(factors.model_reliability))
        + weights["instability"] * (1.0 - _clip01(factors.prediction_stability))
        + weights["lineup_dependency"] * _clip01(factors.lineup_dependency)
    )
    return _clip01(score)


def _log_scale(value: float, low: float, high: float) -> float:
    import math

    value = min(max(value, low), high)
    return (math.log(value) - math.log(low)) / (math.log(high) - math.log(low))


def _clip01(value: float) -> float:
    return min(max(value, 0.0), 1.0)
