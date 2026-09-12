"""Poisson attack/defense model for count-based team markets (corners, cards).

Rationale (see MODEL_SPEC.md for the full comparison): corners and cards are
event counts per team, not goals — they don't share Dixon-Coles's low-score
correlation problem (that correction exists specifically because two
independent Poissons underestimate 0-0/1-1 scorelines, a goals-specific
artifact), so this is a plain Maher-style log-linear Poisson attack/defense
model, not a copy of Dixon-Coles with the tau correction removed for no reason.

Why Poisson and not negative binomial as a first cut: this is a genuine
open modeling question, not a settled choice — corner/card counts often show
overdispersion (variance > mean) in the literature, which a plain Poisson
under-represents (too little probability mass in the tails, i.e. overconfident
probabilities). Starting with Poisson keeps the first implementation simple
and interpretable; BACKTEST_SPEC.md's calibration curve for these markets is
exactly the tool that should tell us whether the overdispersion is bad enough
in practice to justify moving to a negative-binomial version (same
attack/defense structure, one extra dispersion parameter) — that upgrade is
recorded in ROADMAP.md, not done speculatively before there's evidence for it.

Cards specifically: a referee's tendencies are a known driver of card counts
(see MODEL_SPEC.md / the brief itself) but no referee-level data is ingested
yet (see DATA_SOURCES.md on AIA-FIGC/PGMOL), so this model is deliberately
team/opponent-only for now — it will systematically miss referee-driven
variance until that feature exists, which is a known, documented limitation,
not an oversight.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson


@dataclass(frozen=True)
class CountMatchInput:
    home_team: str
    away_team: str
    home_count: int  # e.g. corners won by the home team, or cards shown to the home team
    away_count: int
    match_date: date


@dataclass
class CountModelParams:
    teams: list[str]
    attack: dict[str, float]
    defense: dict[str, float]
    home_advantage: float
    fitted_at: datetime
    training_cutoff: date
    n_matches: int


class PoissonCountModel:
    """Fits and predicts with a Poisson attack/defense/home-advantage model for
    any per-team count statistic (corners, cards, ...). One instance = one
    statistic for one competition — never share a fitted instance between,
    say, corners and cards, since their attack/defense ratings are unrelated."""

    def __init__(self, xi: float = 0.0018) -> None:
        self.xi = xi
        self.params: CountModelParams | None = None

    def fit(self, matches: list[CountMatchInput], as_of: date | None = None) -> CountModelParams:
        if not matches:
            raise ValueError("Cannot fit count model on an empty match list")
        as_of = as_of or max(m.match_date for m in matches)
        teams = sorted({m.home_team for m in matches} | {m.away_team for m in matches})
        n = len(teams)
        team_idx = {t: i for i, t in enumerate(teams)}

        weights = np.array([np.exp(-self.xi * (as_of - m.match_date).days) for m in matches])
        home_idx = np.array([team_idx[m.home_team] for m in matches])
        away_idx = np.array([team_idx[m.away_team] for m in matches])
        home_counts = np.array([m.home_count for m in matches], dtype=float)
        away_counts = np.array([m.away_count for m in matches], dtype=float)
        log_fact_home = np.array([_log_factorial(m.home_count) for m in matches])
        log_fact_away = np.array([_log_factorial(m.away_count) for m in matches])

        def unpack(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
            return x[:n], x[n : 2 * n], x[2 * n]

        def neg_log_likelihood(x: np.ndarray) -> float:
            attack, defense, home_adv = unpack(x)
            lam = np.exp(attack[home_idx] + defense[away_idx] + home_adv)
            mu = np.exp(attack[away_idx] + defense[home_idx])
            log_p = (
                -lam
                + home_counts * np.log(lam)
                - log_fact_home
                - mu
                + away_counts * np.log(mu)
                - log_fact_away
            )
            return float(-(weights * log_p).sum())

        def objective(x: np.ndarray) -> float:
            attack = x[:n]
            penalty = 1000.0 * (attack.mean()) ** 2  # identifiability, same trick as Dixon-Coles
            return neg_log_likelihood(x) + penalty

        x0 = np.zeros(2 * n + 1)
        result = minimize(objective, x0, method="L-BFGS-B")
        attack, defense, home_adv = unpack(result.x)

        self.params = CountModelParams(
            teams=teams,
            attack=dict(zip(teams, attack.tolist())),
            defense=dict(zip(teams, defense.tolist())),
            home_advantage=float(home_adv),
            fitted_at=datetime.now(UTC),
            training_cutoff=as_of,
            n_matches=len(matches),
        )
        return self.params

    def expected_counts(self, home_team: str, away_team: str) -> tuple[float, float]:
        p = self._require_params()
        if home_team not in p.attack or away_team not in p.attack:
            missing = home_team if home_team not in p.attack else away_team
            raise ValueError(f"Team not in fitted model: {missing!r}")
        lam = np.exp(p.attack[home_team] + p.defense[away_team] + p.home_advantage)
        mu = np.exp(p.attack[away_team] + p.defense[home_team])
        return float(lam), float(mu)

    def team_total_probabilities(
        self, home_team: str, away_team: str, side: str, line: float, max_count: int = 30
    ) -> dict[str, float]:
        """Over/Under for one team's own count (e.g. "home corners over/under 5.5")."""
        lam, mu = self.expected_counts(home_team, away_team)
        rate = lam if side == "home" else mu
        counts = np.arange(max_count + 1)
        probs = poisson.pmf(counts, rate)
        return {"OVER": float(probs[counts > line].sum()), "UNDER": float(probs[counts < line].sum())}

    def match_total_probabilities(
        self, home_team: str, away_team: str, line: float, max_count: int = 40
    ) -> dict[str, float]:
        """Over/Under for the match total (home + away). The sum of two independent
        Poisson variables is itself Poisson(lambda + mu) — no need to build a
        joint score matrix the way Dixon-Coles does for goals."""
        lam, mu = self.expected_counts(home_team, away_team)
        counts = np.arange(max_count + 1)
        probs = poisson.pmf(counts, lam + mu)
        return {"OVER": float(probs[counts > line].sum()), "UNDER": float(probs[counts < line].sum())}

    def _require_params(self) -> CountModelParams:
        if self.params is None:
            raise RuntimeError("Model has not been fitted — call .fit(matches) first")
        return self.params


def _log_factorial(n: int) -> float:
    return float(np.sum(np.log(np.arange(1, n + 1)))) if n > 0 else 0.0
