"""Dixon-Coles Poisson goal model for the MATCH_RESULT / TOTAL_GOALS / BTTS markets.

Rationale (see MODEL_SPEC.md for the full comparison of candidate models): a
bivariate-Poisson-style model is the standard, well-validated approach for
full-match goal markets in football, and is directly interpretable (attack/defense
strength ratings, explainable per the project's "spiegabile" requirement) —
unlike a black-box classifier. Two independent Poisson processes underestimate the
frequency of low-scoring draws (0-0, 1-1) relative to reality, which is exactly
the correlation Dixon & Coles (1997, "Modelling Association Football Scores and
Inefficiencies in the Football Betting Market") correct for with the `rho` term
applied to the four low-score cells — this is the classical, peer-reviewed
reference implementation this module follows.

Time-decay weighting (`xi`) down-weights older matches exponentially so the fitted
strengths track a team's *current* level rather than an unweighted historical
average, addressing the brief's "pesatura dinamica basata su recenza" requirement
at the level this model can support; the richer requirements (transferability
factor for promoted teams, coach/system continuity, H2H filtering) are feature
engineering that sits *above* this model, in the data fed to it and in the
Intelligence Engine's signals — this class only fits attack/defense/home-advantage
parameters from whatever match list it is given.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson


@dataclass(frozen=True)
class GoalMatchInput:
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    match_date: date


@dataclass
class DixonColesParams:
    teams: list[str]
    attack: dict[str, float]
    defense: dict[str, float]
    home_advantage: float
    rho: float
    fitted_at: datetime
    training_cutoff: date
    n_matches: int


def _tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    """Dixon-Coles low-score correlation adjustment for cells (0,0),(0,1),(1,0),(1,1)."""
    if x == 0 and y == 0:
        return 1 - lam * mu * rho
    if x == 0 and y == 1:
        return 1 + lam * rho
    if x == 1 and y == 0:
        return 1 + mu * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


class DixonColesModel:
    """Fits and predicts with Dixon-Coles attack/defense/home-advantage parameters."""

    def __init__(self, xi: float = 0.0018) -> None:
        """`xi` is the exponential time-decay rate (per day). 0.0018/day corresponds to
        the value Dixon & Coles found reasonable in their original paper (~half-life
        of roughly one season); it is a starting point to be recalibrated against this
        project's own backtest results (see BACKTEST_SPEC.md), not treated as fixed truth."""
        self.xi = xi
        self.params: DixonColesParams | None = None

    def fit(self, matches: list[GoalMatchInput], as_of: date | None = None) -> DixonColesParams:
        if not matches:
            raise ValueError("Cannot fit Dixon-Coles model on an empty match list")
        as_of = as_of or max(m.match_date for m in matches)
        teams = sorted({m.home_team for m in matches} | {m.away_team for m in matches})
        n = len(teams)
        team_idx = {t: i for i, t in enumerate(teams)}

        # Precompute everything per-match once, as plain numpy arrays, so the
        # optimizer's repeated likelihood evaluations are vectorized instead of
        # re-walking a Python list on every call — this is what keeps a walk-forward
        # backtest with hundreds of refits over thousands of matches tractable.
        weights = np.array([np.exp(-self.xi * (as_of - m.match_date).days) for m in matches])
        home_idx = np.array([team_idx[m.home_team] for m in matches])
        away_idx = np.array([team_idx[m.away_team] for m in matches])
        home_goals = np.array([m.home_goals for m in matches], dtype=float)
        away_goals = np.array([m.away_goals for m in matches], dtype=float)
        log_fact_home = np.array([_log_factorial(m.home_goals) for m in matches])
        log_fact_away = np.array([_log_factorial(m.away_goals) for m in matches])
        is_00 = (home_goals == 0) & (away_goals == 0)
        is_01 = (home_goals == 0) & (away_goals == 1)
        is_10 = (home_goals == 1) & (away_goals == 0)
        is_11 = (home_goals == 1) & (away_goals == 1)

        def unpack(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
            attack = x[:n]
            defense = x[n : 2 * n]
            home_adv = x[2 * n]
            rho = x[2 * n + 1]
            return attack, defense, home_adv, rho

        def neg_log_likelihood(x: np.ndarray) -> float:
            attack, defense, home_adv, rho = unpack(x)
            lam = np.exp(attack[home_idx] + defense[away_idx] + home_adv)
            mu = np.exp(attack[away_idx] + defense[home_idx])

            tau_val = np.ones_like(lam)
            tau_val = np.where(is_00, 1 - lam * mu * rho, tau_val)
            tau_val = np.where(is_01, 1 + lam * rho, tau_val)
            tau_val = np.where(is_10, 1 + mu * rho, tau_val)
            tau_val = np.where(is_11, 1 - rho, tau_val)
            tau_val = np.maximum(tau_val, 1e-10)  # guard against invalid rho region

            log_p = (
                -lam
                + home_goals * np.log(lam)
                - log_fact_home
                - mu
                + away_goals * np.log(mu)
                - log_fact_away
                + np.log(tau_val)
            )
            return float(-(weights * log_p).sum())

        x0 = np.zeros(2 * n + 2)
        x0[2 * n] = 0.2  # home advantage prior
        # Identifiability: fix first team's attack to 0 via a constraint-free
        # reparametrisation is more complex; instead we add a soft penalty pulling
        # attack ratings to mean zero, which is equivalent in effect and keeps the
        # optimizer unconstrained.
        def objective(x: np.ndarray) -> float:
            attack = x[:n]
            penalty = 1000.0 * (attack.mean()) ** 2
            return neg_log_likelihood(x) + penalty

        result = minimize(objective, x0, method="L-BFGS-B")
        attack, defense, home_adv, rho = unpack(result.x)

        self.params = DixonColesParams(
            teams=teams,
            attack=dict(zip(teams, attack.tolist())),
            defense=dict(zip(teams, defense.tolist())),
            home_advantage=float(home_adv),
            rho=float(rho),
            fitted_at=datetime.now(UTC),
            training_cutoff=as_of,
            n_matches=len(matches),
        )
        return self.params

    def expected_goals(self, home_team: str, away_team: str) -> tuple[float, float]:
        p = self._require_params()
        if home_team not in p.attack or away_team not in p.attack:
            raise ValueError(
                f"Team not in fitted model: {home_team if home_team not in p.attack else away_team!r}"
            )
        lam = np.exp(p.attack[home_team] + p.defense[away_team] + p.home_advantage)
        mu = np.exp(p.attack[away_team] + p.defense[home_team])
        return float(lam), float(mu)

    def score_matrix(self, home_team: str, away_team: str, max_goals: int = 10) -> np.ndarray:
        lam, mu = self.expected_goals(home_team, away_team)
        return self.score_matrix_from_expected_goals(lam, mu, max_goals=max_goals)

    def score_matrix_from_expected_goals(self, lam: float, mu: float, max_goals: int = 10) -> np.ndarray:
        """Same tau-adjusted score matrix as `score_matrix`, but for caller-supplied
        (lam, mu) instead of team names — this model's fitted `rho` is still used.
        Lets a layer above this model (e.g. a tactical/xG adjustment — see
        MODEL_SPEC.md) correct the expected-goals inputs without duplicating the
        Dixon-Coles tau-correction math, and without this class needing to know
        anything about where an adjusted lam/mu came from."""
        p = self._require_params()
        home_probs = poisson.pmf(np.arange(max_goals + 1), lam)
        away_probs = poisson.pmf(np.arange(max_goals + 1), mu)
        matrix = np.outer(home_probs, away_probs)
        for x in range(2):
            for y in range(2):
                matrix[x, y] *= _tau(x, y, lam, mu, p.rho)
        matrix /= matrix.sum()  # renormalize after the tau adjustment and goal truncation
        return matrix

    def match_result_probabilities(
        self, home_team: str, away_team: str, max_goals: int = 10
    ) -> dict[str, float]:
        matrix = self.score_matrix(home_team, away_team, max_goals)
        home_win = float(np.tril(matrix, -1).sum())
        draw = float(np.trace(matrix))
        away_win = float(np.triu(matrix, 1).sum())
        return {"HOME": home_win, "DRAW": draw, "AWAY": away_win}

    def total_goals_probabilities(
        self, home_team: str, away_team: str, line: float = 2.5, max_goals: int = 10
    ) -> dict[str, float]:
        matrix = self.score_matrix(home_team, away_team, max_goals)
        totals = np.add.outer(np.arange(max_goals + 1), np.arange(max_goals + 1))
        over = float(matrix[totals > line].sum())
        under = float(matrix[totals < line].sum())
        return {"OVER": over, "UNDER": under}

    def btts_probabilities(self, home_team: str, away_team: str, max_goals: int = 10) -> dict[str, float]:
        matrix = self.score_matrix(home_team, away_team, max_goals)
        yes = float(matrix[1:, 1:].sum())
        no = float(1.0 - yes)
        return {"YES": yes, "NO": no}

    def _require_params(self) -> DixonColesParams:
        if self.params is None:
            raise RuntimeError("Model has not been fitted — call .fit(matches) first")
        return self.params


def _log_factorial(n: int) -> float:
    return float(np.sum(np.log(np.arange(1, n + 1)))) if n > 0 else 0.0
