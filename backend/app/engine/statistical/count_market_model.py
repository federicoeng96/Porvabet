"""Attack/defense count models for corners/cards markets: Poisson and negative
binomial, both fitted, both backtested — see BACKTEST_SPEC.md "Poisson vs
negative binomiale" for the actual comparison that decided which one
`count_market_estimates.py` uses in production, and why. This module
deliberately keeps both classes rather than deleting the loser, so the
comparison stays reproducible and either can be reinstated if a future,
larger backtest changes the picture.

Rationale (see MODEL_SPEC.md for the full comparison): corners and cards are
event counts per team, not goals — they don't share Dixon-Coles's low-score
correlation problem (that correction exists specifically because two
independent Poissons underestimate 0-0/1-1 scorelines, a goals-specific
artifact), so both models here are plain Maher-style log-linear attack/defense
models, not a copy of Dixon-Coles with the tau correction removed for no
reason.

Why both: corner/card counts often show overdispersion (variance > mean) in
the literature, which a plain Poisson under-represents (too little
probability mass in the tails, i.e. overconfident probabilities) — an initial
real backtest on this project's own data confirmed exactly that pattern
(marked overconfidence above p=0.7, see BACKTEST_SPEC.md). The negative
binomial below adds one dispersion parameter (shared across teams) to the
same attack/defense structure, which should absorb that overdispersion IF
it's really about the count distribution's shape and not, say, the
attack/defense mean structure itself being too crude — which is exactly the
kind of thing that has to be checked with backtest numbers, not assumed.

Cards specifically: a referee's tendencies are a known driver of card counts
(see MODEL_SPEC.md / the brief itself) but no referee-level data is ingested
yet (see DATA_SOURCES.md on AIA-FIGC/PGMOL), so both models here are
deliberately team/opponent-only for now — they will systematically miss
referee-driven variance until that feature exists, which is a known,
documented limitation, not an oversight.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import nbinom, poisson


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


@dataclass
class NBCountModelParams:
    teams: list[str]
    attack: dict[str, float]
    defense: dict[str, float]
    home_advantage: float
    alpha: float  # dispersion parameter, shared across teams; variance = mu + alpha*mu^2
    fitted_at: datetime
    training_cutoff: date
    n_matches: int


class NegativeBinomialCountModel:
    """Same attack/defense/home-advantage structure as PoissonCountModel, plus
    one shared dispersion parameter `alpha` (NB2 parameterization: variance =
    mu + alpha*mu^2, alpha->0 recovers Poisson). `alpha` is fitted jointly with
    the attack/defense ratings via MLE, not set by hand.

    Unlike Poisson, the sum of two negative-binomial variables with a shared
    dispersion but different means has no closed form (it does for Poisson,
    and for NB only when the two also share the same success probability,
    which they don't here since home/away means differ) — so
    `match_total_probabilities` computes the match-total distribution by
    explicit convolution of the two teams' count distributions instead.
    """

    def __init__(self, xi: float = 0.0018) -> None:
        self.xi = xi
        self.params: NBCountModelParams | None = None

    def fit(self, matches: list[CountMatchInput], as_of: date | None = None) -> NBCountModelParams:
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

        def unpack(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
            attack, defense, home_adv, log_alpha = x[:n], x[n : 2 * n], x[2 * n], x[2 * n + 1]
            # Clip before exponentiating: L-BFGS-B can probe extreme log_alpha
            # values mid-search: exp(-1000) underflows to an exact 0.0, and
            # 1/alpha then raises ZeroDivisionError. +-20 covers alpha from
            # ~2e-9 (indistinguishable from Poisson) to ~5e8 (absurdly
            # overdispersed) — nowhere near where a real optimum would land,
            # so clipping here never constrains a genuine fit.
            log_alpha = float(np.clip(log_alpha, -20.0, 20.0))
            return attack, defense, home_adv, float(np.exp(log_alpha))

        def nb_log_pmf(counts: np.ndarray, mu: np.ndarray, r: float) -> np.ndarray:
            # NB2: r = 1/alpha "successes", p = r/(r+mu).
            return (
                gammaln(counts + r)
                - gammaln(r)
                - gammaln(counts + 1)
                + r * np.log(r / (r + mu))
                + counts * np.log(mu / (r + mu))
            )

        def neg_log_likelihood(x: np.ndarray) -> float:
            attack, defense, home_adv, alpha = unpack(x)
            r = 1.0 / alpha
            mu_home = np.exp(attack[home_idx] + defense[away_idx] + home_adv)
            mu_away = np.exp(attack[away_idx] + defense[home_idx])
            log_p = nb_log_pmf(home_counts, mu_home, r) + nb_log_pmf(away_counts, mu_away, r)
            return float(-(weights * log_p).sum())

        def objective(x: np.ndarray) -> float:
            attack = x[:n]
            penalty = 1000.0 * (attack.mean()) ** 2  # identifiability, same trick as Dixon-Coles
            return neg_log_likelihood(x) + penalty

        x0 = np.zeros(2 * n + 2)
        x0[2 * n + 1] = np.log(0.1)  # alpha=0.1 starting guess (mild overdispersion)
        result = minimize(objective, x0, method="L-BFGS-B")
        attack, defense, home_adv, alpha = unpack(result.x)

        self.params = NBCountModelParams(
            teams=teams,
            attack=dict(zip(teams, attack.tolist())),
            defense=dict(zip(teams, defense.tolist())),
            home_advantage=float(home_adv),
            alpha=alpha,
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

    def _team_pmf(self, mu: float, max_count: int) -> np.ndarray:
        p = self._require_params()
        r = 1.0 / p.alpha
        nb_p = r / (r + mu)  # scipy's nbinom(n, p) has mean n(1-p)/p
        counts = np.arange(max_count + 1)
        return nbinom.pmf(counts, r, nb_p)

    def team_total_probabilities(
        self, home_team: str, away_team: str, side: str, line: float, max_count: int = 30
    ) -> dict[str, float]:
        lam, mu = self.expected_counts(home_team, away_team)
        rate = lam if side == "home" else mu
        probs = self._team_pmf(rate, max_count)
        counts = np.arange(max_count + 1)
        return {"OVER": float(probs[counts > line].sum()), "UNDER": float(probs[counts < line].sum())}

    def match_total_probabilities(
        self, home_team: str, away_team: str, line: float, max_count: int = 40
    ) -> dict[str, float]:
        """No closed form for the sum (see class docstring) — convolve the two
        teams' count distributions explicitly instead."""
        lam, mu = self.expected_counts(home_team, away_team)
        home_pmf = self._team_pmf(lam, max_count)
        away_pmf = self._team_pmf(mu, max_count)
        total_pmf = np.convolve(home_pmf, away_pmf)[: max_count + 1]
        total_pmf = total_pmf / total_pmf.sum()  # renormalize after truncation
        counts = np.arange(len(total_pmf))
        return {"OVER": float(total_pmf[counts > line].sum()), "UNDER": float(total_pmf[counts < line].sum())}

    def _require_params(self) -> NBCountModelParams:
        if self.params is None:
            raise RuntimeError("Model has not been fitted — call .fit(matches) first")
        return self.params


@dataclass
class NBPerTeamCountModelParams:
    teams: list[str]
    attack: dict[str, float]
    defense: dict[str, float]
    home_advantage: float
    alpha: dict[str, float]  # one dispersion parameter per team, not shared
    fitted_at: datetime
    training_cutoff: date
    n_matches: int


class NegativeBinomialPerTeamCountModel:
    """Same as `NegativeBinomialCountModel`, but with one dispersion parameter
    `alpha` per team instead of one shared across the whole competition — the
    honest follow-up hypothesis BACKTEST_SPEC.md's Poisson-vs-NB comparison
    flagged as untried ("un parametro di dispersione condiviso fra tutte le
    squadre non compensa..."; a shared alpha assumes every team's count
    variance is equally under/over-dispersed relative to its mean, which is
    an assumption, not a finding). A team's own count uses its own alpha
    regardless of home/away role (e.g. a team's corners-won distribution is
    modeled with that team's alpha whether it's playing home or away) —
    dispersion is treated as a team property of the count process, not a
    role property.

    Real backtest result (see BACKTEST_SPEC.md): does not resolve the
    high-tail overconfidence any more consistently than the shared-alpha
    version, at a much higher compute cost (3x more parameters, single fits
    taking 10-25s on this project's real dataset vs ~1-3s shared) — kept in
    the codebase, tested and functioning, exactly like `NegativeBinomialCountModel`
    itself, not deleted after a negative result.
    """

    def __init__(self, xi: float = 0.0018) -> None:
        self.xi = xi
        self.params: NBPerTeamCountModelParams | None = None

    def fit(self, matches: list[CountMatchInput], as_of: date | None = None) -> NBPerTeamCountModelParams:
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

        def unpack(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
            attack, defense, home_adv = x[:n], x[n : 2 * n], x[2 * n]
            log_alpha_team = np.clip(x[2 * n + 1 : 3 * n + 1], -20.0, 20.0)  # same clip rationale
            # as the shared-alpha model above — an unclipped extreme here
            # underflows exp() to 0.0 and 1/alpha then raises ZeroDivisionError.
            return attack, defense, float(home_adv), np.exp(log_alpha_team)

        def nb_log_pmf(counts: np.ndarray, mu: np.ndarray, r: np.ndarray) -> np.ndarray:
            return (
                gammaln(counts + r)
                - gammaln(r)
                - gammaln(counts + 1)
                + r * np.log(r / (r + mu))
                + counts * np.log(mu / (r + mu))
            )

        def neg_log_likelihood(x: np.ndarray) -> float:
            attack, defense, home_adv, alpha_team = unpack(x)
            mu_home = np.exp(attack[home_idx] + defense[away_idx] + home_adv)
            mu_away = np.exp(attack[away_idx] + defense[home_idx])
            # Each side's count uses the alpha of the team whose count it is
            # (the home team's own dispersion for its own corners/cards/fouls
            # total, not the opponent's) — a team property, not a role property.
            r_home = 1.0 / alpha_team[home_idx]
            r_away = 1.0 / alpha_team[away_idx]
            log_p = nb_log_pmf(home_counts, mu_home, r_home) + nb_log_pmf(away_counts, mu_away, r_away)
            return float(-(weights * log_p).sum())

        def objective(x: np.ndarray) -> float:
            attack = x[:n]
            penalty = 1000.0 * (attack.mean()) ** 2
            return neg_log_likelihood(x) + penalty

        x0 = np.zeros(3 * n + 1)
        x0[2 * n + 1 :] = np.log(0.1)  # same starting guess as the shared-alpha model, per team
        # A higher iteration/function-eval cap than scipy's L-BFGS-B default is
        # required here: with 3n+1 parameters (n teams) instead of 2n+2, this
        # problem needs meaningfully more evaluations to reach the same
        # relative-reduction convergence criterion — verified empirically
        # against this project's own real EPL corners data (34 teams, 103
        # parameters) during this session's investigation.
        result = minimize(objective, x0, method="L-BFGS-B", options={"maxfun": 50000, "maxiter": 50000})
        attack, defense, home_adv, alpha_team = unpack(result.x)

        self.params = NBPerTeamCountModelParams(
            teams=teams,
            attack=dict(zip(teams, attack.tolist())),
            defense=dict(zip(teams, defense.tolist())),
            home_advantage=home_adv,
            alpha=dict(zip(teams, alpha_team.tolist())),
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

    def _team_pmf(self, mu: float, alpha: float, max_count: int) -> np.ndarray:
        r = 1.0 / alpha
        nb_p = r / (r + mu)
        counts = np.arange(max_count + 1)
        return nbinom.pmf(counts, r, nb_p)

    def team_total_probabilities(
        self, home_team: str, away_team: str, side: str, line: float, max_count: int = 30
    ) -> dict[str, float]:
        p = self._require_params()
        lam, mu = self.expected_counts(home_team, away_team)
        rate = lam if side == "home" else mu
        team = home_team if side == "home" else away_team
        probs = self._team_pmf(rate, p.alpha[team], max_count)
        counts = np.arange(max_count + 1)
        return {"OVER": float(probs[counts > line].sum()), "UNDER": float(probs[counts < line].sum())}

    def match_total_probabilities(
        self, home_team: str, away_team: str, line: float, max_count: int = 40
    ) -> dict[str, float]:
        """No closed form for the sum (same reason as the shared-alpha model
        — here the two sides don't even share a dispersion parameter, let
        alone a success probability) — convolve explicitly."""
        p = self._require_params()
        lam, mu = self.expected_counts(home_team, away_team)
        home_pmf = self._team_pmf(lam, p.alpha[home_team], max_count)
        away_pmf = self._team_pmf(mu, p.alpha[away_team], max_count)
        total_pmf = np.convolve(home_pmf, away_pmf)[: max_count + 1]
        total_pmf = total_pmf / total_pmf.sum()
        counts = np.arange(len(total_pmf))
        return {"OVER": float(total_pmf[counts > line].sum()), "UNDER": float(total_pmf[counts < line].sum())}

    def _require_params(self) -> NBPerTeamCountModelParams:
        if self.params is None:
            raise RuntimeError("Model has not been fitted — call .fit(matches) first")
        return self.params


def _log_factorial(n: int) -> float:
    return float(np.sum(np.log(np.arange(1, n + 1)))) if n > 0 else 0.0
