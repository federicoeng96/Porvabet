"""Tests the Dixon-Coles model against SYNTHETIC, programmatically generated
match data (clearly not real results) — checking mathematical/statistical
properties (probabilities sum to 1, stronger teams favored, home advantage
recovered) rather than any specific real-world figure."""

import random
from datetime import date, timedelta

import pytest

from app.engine.statistical.dixon_coles import DixonColesModel, GoalMatchInput


def _synthetic_matches(seed: int = 42, n: int = 400) -> list[GoalMatchInput]:
    rng = random.Random(seed)
    teams = ["Strong", "Medium", "Weak"]
    true_strength = {"Strong": 2.0, "Medium": 1.2, "Weak": 0.6}
    start = date(2023, 8, 1)
    matches = []
    for i in range(n):
        home, away = rng.sample(teams, 2)
        lam = true_strength[home] * 1.3
        mu = true_strength[away]
        home_goals = min(int(rng.gammavariate(lam, 1)), 8)
        away_goals = min(int(rng.gammavariate(mu, 1)), 8)
        matches.append(GoalMatchInput(home, away, home_goals, away_goals, start + timedelta(days=i)))
    return matches


@pytest.fixture()
def fitted_model() -> DixonColesModel:
    matches = _synthetic_matches()
    model = DixonColesModel()
    model.fit(matches, as_of=matches[-1].match_date + timedelta(days=1))
    return model


def test_match_result_probabilities_sum_to_one(fitted_model):
    probs = fitted_model.match_result_probabilities("Strong", "Weak")
    assert sum(probs.values()) == pytest.approx(1.0, abs=1e-6)
    assert all(0 <= p <= 1 for p in probs.values())


def test_stronger_team_favored_at_home(fitted_model):
    probs = fitted_model.match_result_probabilities("Strong", "Weak")
    assert probs["HOME"] > probs["AWAY"]
    assert probs["HOME"] > probs["DRAW"]


def test_home_advantage_is_positive(fitted_model):
    assert fitted_model.params.home_advantage > 0


def test_total_goals_probabilities_sum_to_one(fitted_model):
    probs = fitted_model.total_goals_probabilities("Strong", "Medium", line=2.5)
    assert sum(probs.values()) == pytest.approx(1.0, abs=1e-6)


def test_btts_probabilities_sum_to_one(fitted_model):
    probs = fitted_model.btts_probabilities("Strong", "Weak")
    assert sum(probs.values()) == pytest.approx(1.0, abs=1e-6)


def test_predict_unknown_team_raises(fitted_model):
    with pytest.raises(ValueError):
        fitted_model.match_result_probabilities("Strong", "NeverSeenTeam")


def test_fit_requires_at_least_one_match():
    with pytest.raises(ValueError):
        DixonColesModel().fit([])


def test_predict_before_fit_raises():
    model = DixonColesModel()
    with pytest.raises(RuntimeError):
        model.match_result_probabilities("A", "B")
