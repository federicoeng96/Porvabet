"""Post-hoc probability calibration — Platt scaling and isotonic regression,
as two testable, independently fittable options (ROADMAP.md "Calibrazione dei
pesi/soglie/probabilità").

Both take the model's raw probability and correct it toward the empirically
observed win rate, using only already-resolved (probability, outcome) pairs —
same leak-free discipline as everything else in `app/backtest/`: a calibrator
must only ever be fit on predictions strictly earlier than whatever it is
later applied to (see `app/backtest/calibration_runner.py` for how the
walk-forward split enforces this).

**Platt scaling** (`PlattCalibrator`): fits a 2-parameter logistic transform
`calibrated = sigmoid(a * logit(raw) + b)` by maximum likelihood (same
scipy.optimize approach already used for Dixon-Coles/count models elsewhere in
this codebase). A fixed, low-parameter functional form — robust with the
modest sample sizes available in the high-probability bins where BACKTEST_SPEC.md
documents the overconfidence problem (as few as n=38-50).

**Isotonic regression** (`IsotonicCalibrator`): a non-parametric, monotonic
step function fit via the Pool Adjacent Violators Algorithm (PAVA, implemented
directly below — no scikit-learn dependency for one algorithm). More flexible
than Platt scaling, but that flexibility is exactly what can overfit a sparse
bin — the two are deliberately kept as separate, comparable options rather
than picking one a priori; see BACKTEST_SPEC.md for which (if either) the real
backtest comparison actually justifies activating.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.backtest.metrics import BetRecord

_EPS = 1e-6


def _logit(p: float) -> float:
    p = min(max(p, _EPS), 1 - _EPS)
    return math.log(p / (1 - p))


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


@dataclass(frozen=True)
class PlattCalibrator:
    a: float
    b: float

    def calibrate(self, probability: float) -> float:
        return _sigmoid(self.a * _logit(probability) + self.b)


def fit_platt_calibration(bets: list[BetRecord]) -> PlattCalibrator:
    """MLE fit of (a, b) minimizing log loss on `bets`. Starting point (1, 0)
    is the identity transform — if the raw probabilities are already
    well-calibrated, the optimizer should stay close to it."""
    from scipy.optimize import minimize

    x = [_logit(b.probability) for b in bets]
    y = [1.0 if b.won else 0.0 for b in bets]

    def neg_log_likelihood(params: tuple[float, float]) -> float:
        a, b = params
        total = 0.0
        for xi, yi in zip(x, y, strict=True):
            p = _sigmoid(a * xi + b)
            p = min(max(p, _EPS), 1 - _EPS)
            total -= yi * math.log(p) + (1 - yi) * math.log(1 - p)
        return total / len(x)

    result = minimize(neg_log_likelihood, x0=[1.0, 0.0], method="Nelder-Mead")
    a, b = result.x
    return PlattCalibrator(a=float(a), b=float(b))


@dataclass(frozen=True)
class IsotonicCalibrator:
    # Fitted (raw_probability, calibrated_probability) breakpoints, sorted by
    # raw_probability ascending, calibrated values non-decreasing (the PAVA
    # invariant) — `calibrate` linearly interpolates between them and clips
    # outside the observed range, same convention as sklearn's IsotonicRegression.
    xs: tuple[float, ...]
    ys: tuple[float, ...]

    def calibrate(self, probability: float) -> float:
        xs, ys = self.xs, self.ys
        if probability <= xs[0]:
            return ys[0]
        if probability >= xs[-1]:
            return ys[-1]
        for i in range(1, len(xs)):
            if probability <= xs[i]:
                x0, x1 = xs[i - 1], xs[i]
                y0, y1 = ys[i - 1], ys[i]
                if x1 == x0:
                    return y1
                t = (probability - x0) / (x1 - x0)
                return y0 + t * (y1 - y0)
        return ys[-1]


def fit_isotonic_calibration(bets: list[BetRecord]) -> IsotonicCalibrator:
    """Pool Adjacent Violators Algorithm: fits the monotonic non-decreasing
    step function that best fits (raw probability -> observed outcome) in a
    least-squares sense, then de-duplicates repeated x values (averaging their
    fitted level) so `calibrate` can interpolate on a strictly increasing x."""
    ordered = sorted(bets, key=lambda b: b.probability)
    xs_raw = [b.probability for b in ordered]
    ys_raw = [1.0 if b.won else 0.0 for b in ordered]

    # Each block: [sum_y, weight, start_idx, end_idx]. A weight of 1 per bet
    # (no differential weighting) — PAVA merges adjacent blocks whenever the
    # next block's mean would violate monotonicity with the previous one.
    blocks: list[list[float]] = []
    for y in ys_raw:
        blocks.append([y, 1.0])
        while len(blocks) > 1 and (blocks[-2][0] / blocks[-2][1]) > (blocks[-1][0] / blocks[-1][1]):
            s2, w2 = blocks.pop()
            s1, w1 = blocks.pop()
            blocks.append([s1 + s2, w1 + w2])

    fitted = []
    for s, w in blocks:
        fitted.extend([s / w] * int(w))

    # Collapse repeated x values (ties in raw probability) to one point,
    # averaging their fitted level — keeps `calibrate`'s interpolation
    # well-defined (strictly increasing xs).
    dedup_xs: list[float] = []
    dedup_ys: list[float] = []
    i = 0
    n = len(xs_raw)
    while i < n:
        j = i
        while j < n and xs_raw[j] == xs_raw[i]:
            j += 1
        dedup_xs.append(xs_raw[i])
        dedup_ys.append(sum(fitted[i:j]) / (j - i))
        i = j

    return IsotonicCalibrator(xs=tuple(dedup_xs), ys=tuple(dedup_ys))
