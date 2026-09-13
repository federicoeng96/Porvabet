"""Tests the count models (corners/cards/fouls) against SYNTHETIC data —
checking statistical properties, not any specific real-world figure.
Parametrized across all three model classes since they share the same public
interface (fit/expected_counts/team_total_probabilities/
match_total_probabilities) — see BACKTEST_SPEC.md for which one production
actually uses and why."""

import random
from datetime import date, timedelta

import pytest

from app.engine.statistical.count_market_model import (
    CountMatchInput,
    NegativeBinomialCountModel,
    NegativeBinomialPerTeamCountModel,
    PoissonCountModel,
)

MODEL_CLASSES = [PoissonCountModel, NegativeBinomialCountModel, NegativeBinomialPerTeamCountModel]


def _synthetic_matches(seed: int = 7, n: int = 300) -> list[CountMatchInput]:
    rng = random.Random(seed)
    teams = ["Attacking", "Balanced", "Defensive"]
    true_rate = {"Attacking": 7.0, "Balanced": 5.0, "Defensive": 3.0}
    start = date(2023, 8, 1)
    matches = []
    for i in range(n):
        home, away = rng.sample(teams, 2)
        lam = true_rate[home] * 1.15
        mu = true_rate[away] * 0.9
        home_count = max(0, int(rng.gauss(lam, 2)))
        away_count = max(0, int(rng.gauss(mu, 2)))
        matches.append(CountMatchInput(home, away, home_count, away_count, start + timedelta(days=i)))
    return matches


def _fit(model_cls, matches=None):
    matches = matches or _synthetic_matches()
    model = model_cls()
    model.fit(matches, as_of=matches[-1].match_date + timedelta(days=1))
    return model


@pytest.mark.parametrize("model_cls", MODEL_CLASSES)
def test_attacking_team_has_higher_attack_rating(model_cls):
    model = _fit(model_cls)
    assert model.params.attack["Attacking"] > model.params.attack["Defensive"]


@pytest.mark.parametrize("model_cls", MODEL_CLASSES)
def test_team_total_probabilities_sum_to_one(model_cls):
    model = _fit(model_cls)
    probs = model.team_total_probabilities("Attacking", "Defensive", side="home", line=5.5)
    assert sum(probs.values()) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("model_cls", MODEL_CLASSES)
def test_match_total_probabilities_sum_to_one(model_cls):
    model = _fit(model_cls)
    probs = model.match_total_probabilities("Attacking", "Defensive", line=9.5)
    assert sum(probs.values()) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("model_cls", MODEL_CLASSES)
def test_stronger_attacking_team_more_likely_over(model_cls):
    model = _fit(model_cls)
    strong = model.team_total_probabilities("Attacking", "Defensive", side="home", line=5.5)
    weak = model.team_total_probabilities("Defensive", "Attacking", side="home", line=5.5)
    assert strong["OVER"] > weak["OVER"]


@pytest.mark.parametrize("model_cls", MODEL_CLASSES)
def test_fit_requires_at_least_one_match(model_cls):
    with pytest.raises(ValueError):
        model_cls().fit([])


@pytest.mark.parametrize("model_cls", MODEL_CLASSES)
def test_predict_before_fit_raises(model_cls):
    model = model_cls()
    with pytest.raises(RuntimeError):
        model.expected_counts("A", "B")


@pytest.mark.parametrize("model_cls", MODEL_CLASSES)
def test_predict_unknown_team_raises(model_cls):
    model = _fit(model_cls)
    with pytest.raises(ValueError):
        model.expected_counts("Attacking", "NeverSeenTeam")


def test_negative_binomial_recovers_positive_dispersion_on_overdispersed_data():
    """On data simulated with extra variance beyond a Poisson's mean=variance
    assumption, the fitted alpha should be meaningfully positive (indicating
    the model detects overdispersion), not collapse to ~0 (which would mean
    "no better than Poisson")."""
    rng = random.Random(42)
    teams = ["A", "B", "C", "D"]
    rate = {t: rng.uniform(3.0, 8.0) for t in teams}
    start = date(2022, 8, 1)
    matches = []
    for i in range(250):
        home, away = rng.sample(teams, 2)
        # Wide gaussian noise well beyond Poisson variance = mean, to simulate
        # genuine overdispersion.
        home_count = max(0, int(rng.gauss(rate[home], 4)))
        away_count = max(0, int(rng.gauss(rate[away], 4)))
        matches.append(CountMatchInput(home, away, home_count, away_count, start + timedelta(days=i)))

    model = NegativeBinomialCountModel()
    params = model.fit(matches, as_of=matches[-1].match_date + timedelta(days=1))
    assert params.alpha > 0.05


def test_negative_binomial_per_team_recovers_positive_dispersion_per_team():
    """Same synthetic-overdispersion check as the shared-alpha version above,
    but per team: each team's own fitted alpha should be meaningfully
    positive, not just one shared value."""
    rng = random.Random(42)
    teams = ["A", "B", "C", "D"]
    rate = {t: rng.uniform(3.0, 8.0) for t in teams}
    start = date(2022, 8, 1)
    matches = []
    for i in range(250):
        home, away = rng.sample(teams, 2)
        home_count = max(0, int(rng.gauss(rate[home], 4)))
        away_count = max(0, int(rng.gauss(rate[away], 4)))
        matches.append(CountMatchInput(home, away, home_count, away_count, start + timedelta(days=i)))

    model = NegativeBinomialPerTeamCountModel()
    params = model.fit(matches, as_of=matches[-1].match_date + timedelta(days=1))
    assert set(params.alpha) == set(teams)
    for team in teams:
        assert params.alpha[team] > 0.05


def test_negative_binomial_per_team_uses_each_teams_own_alpha():
    """A team with much noisier (higher-variance) counts than another should
    fit a distinctly higher alpha for itself — not one value forced onto
    both, which is exactly the limitation a shared alpha has."""
    rng = random.Random(11)
    teams = ["Noisy", "Steady"]
    start = date(2022, 8, 1)
    matches = []
    for i in range(400):
        home, away = teams if i % 2 == 0 else teams[::-1]
        home_count = max(0, int(rng.gauss(5.0, 4.0 if home == "Noisy" else 0.5)))
        away_count = max(0, int(rng.gauss(5.0, 4.0 if away == "Noisy" else 0.5)))
        matches.append(CountMatchInput(home, away, home_count, away_count, start + timedelta(days=i)))

    model = NegativeBinomialPerTeamCountModel()
    params = model.fit(matches, as_of=matches[-1].match_date + timedelta(days=1))
    assert params.alpha["Noisy"] > params.alpha["Steady"]
