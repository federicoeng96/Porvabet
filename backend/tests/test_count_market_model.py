"""Tests the Poisson count model (corners/cards) against SYNTHETIC data —
checking statistical properties, not any specific real-world figure."""

import random
from datetime import date, timedelta

import pytest

from app.engine.statistical.count_market_model import CountMatchInput, PoissonCountModel


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


@pytest.fixture()
def fitted_model() -> PoissonCountModel:
    matches = _synthetic_matches()
    model = PoissonCountModel()
    model.fit(matches, as_of=matches[-1].match_date + timedelta(days=1))
    return model


def test_attacking_team_has_higher_attack_rating(fitted_model):
    assert fitted_model.params.attack["Attacking"] > fitted_model.params.attack["Defensive"]


def test_team_total_probabilities_sum_to_one(fitted_model):
    probs = fitted_model.team_total_probabilities("Attacking", "Defensive", side="home", line=5.5)
    assert sum(probs.values()) == pytest.approx(1.0, abs=1e-6)


def test_match_total_probabilities_sum_to_one(fitted_model):
    probs = fitted_model.match_total_probabilities("Attacking", "Defensive", line=9.5)
    assert sum(probs.values()) == pytest.approx(1.0, abs=1e-6)


def test_stronger_attacking_team_more_likely_over(fitted_model):
    strong = fitted_model.team_total_probabilities("Attacking", "Defensive", side="home", line=5.5)
    weak = fitted_model.team_total_probabilities("Defensive", "Attacking", side="home", line=5.5)
    assert strong["OVER"] > weak["OVER"]


def test_fit_requires_at_least_one_match():
    with pytest.raises(ValueError):
        PoissonCountModel().fit([])


def test_predict_before_fit_raises():
    model = PoissonCountModel()
    with pytest.raises(RuntimeError):
        model.expected_counts("A", "B")


def test_predict_unknown_team_raises(fitted_model):
    with pytest.raises(ValueError):
        fitted_model.expected_counts("Attacking", "NeverSeenTeam")
