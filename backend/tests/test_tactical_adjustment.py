"""Tests for the xG-based Dixon-Coles adjustment (MODEL_SPEC.md /
BACKTEST_SPEC.md "xG-adjusted Dixon-Coles") — SYNTHETIC teams/matches."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.engine.statistical.tactical_adjustment import (
    FACTOR_CLIP_RANGE,
    MIN_MATCHES_FOR_FACTOR,
    apply_tactical_adjustment,
    compute_deep_completions_adjustment_factor,
    compute_xg_adjustment_factor,
)
from app.ingestion.match_ingestion import (
    get_or_create_competition,
    get_or_create_season,
    get_or_create_team,
)
from app.models.match import Match
from app.models.stats import TacticalFeature

CUTOFF = date(2024, 1, 1)


def _seed_match_with_xg(db_session, season, home, away, match_date, home_goals, away_goals, home_xg, away_xg):
    match = Match(
        season_id=season.id,
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_utc=datetime(match_date.year, match_date.month, match_date.day, 15, 0, tzinfo=UTC),
        home_goals_ft=home_goals,
        away_goals_ft=away_goals,
    )
    db_session.add(match)
    db_session.flush()
    db_session.add(TacticalFeature(team_id=home.id, as_of_date=match_date, feature_name="xg", value=home_xg, window_matches=1))
    db_session.add(TacticalFeature(team_id=away.id, as_of_date=match_date, feature_name="xg", value=away_xg, window_matches=1))
    db_session.flush()
    return match


def _seed_team_history(db_session, team_name, other_name, n_matches, actual_goals, xg_per_match):
    competition = get_or_create_competition(db_session, "EPL")
    season = get_or_create_season(db_session, competition, "2023/2024")
    team = get_or_create_team(db_session, team_name)
    opponent = get_or_create_team(db_session, other_name)
    db_session.flush()
    start = CUTOFF - timedelta(days=7 * (n_matches + 1))
    for i in range(n_matches):
        _seed_match_with_xg(
            db_session, season, team, opponent, start + timedelta(days=7 * i),
            home_goals=actual_goals, away_goals=0, home_xg=xg_per_match, away_xg=0.5,
        )
    return team


def test_returns_none_with_too_few_matches(db_session):
    team = _seed_team_history(db_session, "Synth Tac A", "Synth Tac Opp A", n_matches=2, actual_goals=1, xg_per_match=2.0)
    assert 2 < MIN_MATCHES_FOR_FACTOR

    factor = compute_xg_adjustment_factor(db_session, team.id, as_of=CUTOFF)
    assert factor is None


def test_underperforming_team_gets_factor_above_one(db_session):
    # xG=2.0 but only scoring 1 goal/match -> team creates better chances than
    # it converts -> factor > 1 (model should expect more goals going forward).
    team = _seed_team_history(db_session, "Synth Tac B", "Synth Tac Opp B", n_matches=6, actual_goals=1, xg_per_match=2.0)

    factor = compute_xg_adjustment_factor(db_session, team.id, as_of=CUTOFF)
    assert factor is not None
    assert factor > 1.0


def test_overperforming_team_gets_factor_below_one(db_session):
    team = _seed_team_history(db_session, "Synth Tac C", "Synth Tac Opp C", n_matches=6, actual_goals=3, xg_per_match=1.0)

    factor = compute_xg_adjustment_factor(db_session, team.id, as_of=CUTOFF)
    assert factor is not None
    assert factor < 1.0


def test_factor_is_clipped_to_safety_range(db_session):
    # Extreme, unrealistic underperformance (xG=10, goals=1) — must not
    # translate into an unbounded correction.
    team = _seed_team_history(db_session, "Synth Tac D", "Synth Tac Opp D", n_matches=6, actual_goals=1, xg_per_match=10.0)

    factor = compute_xg_adjustment_factor(db_session, team.id, as_of=CUTOFF)
    assert factor == pytest.approx(FACTOR_CLIP_RANGE[1])


def test_leak_free_ignores_matches_on_or_after_as_of(db_session):
    team = _seed_team_history(db_session, "Synth Tac E", "Synth Tac Opp E", n_matches=6, actual_goals=1, xg_per_match=2.0)
    # A future (relative to CUTOFF) match with wildly different stats must not
    # affect the factor computed as-of CUTOFF.
    competition = get_or_create_competition(db_session, "EPL")
    season = get_or_create_season(db_session, competition, "2023/2024")
    opponent = get_or_create_team(db_session, "Synth Tac Future Opp")
    db_session.flush()
    _seed_match_with_xg(
        db_session, season, team, opponent, CUTOFF + timedelta(days=7),
        home_goals=5, away_goals=0, home_xg=0.1, away_xg=0.1,
    )

    factor = compute_xg_adjustment_factor(db_session, team.id, as_of=CUTOFF)
    assert factor is not None
    assert factor > 1.0  # unaffected by the post-cutoff overperformance


def test_apply_tactical_adjustment_multiplies_when_factor_present():
    lam, mu = apply_tactical_adjustment(1.5, 1.2, home_factor=1.2, away_factor=0.9)
    assert lam == pytest.approx(1.8)
    assert mu == pytest.approx(1.08)


def test_apply_tactical_adjustment_passes_through_when_factor_is_none():
    lam, mu = apply_tactical_adjustment(1.5, 1.2, home_factor=None, away_factor=None)
    assert lam == 1.5
    assert mu == 1.2


def _seed_deep_values(db_session, team, values, start):
    for i, v in enumerate(values):
        db_session.add(
            TacticalFeature(
                team_id=team.id,
                as_of_date=start + timedelta(days=7 * i),
                feature_name="deep",
                value=v,
                window_matches=1,
            )
        )
    db_session.flush()


def test_deep_completions_factor_above_one_for_above_average_team(db_session):
    league_start = CUTOFF - timedelta(days=100)
    high_team = get_or_create_team(db_session, "Synth Deep High")
    low_team = get_or_create_team(db_session, "Synth Deep Low")
    db_session.flush()
    _seed_deep_values(db_session, high_team, [12.0] * 6, league_start)
    _seed_deep_values(db_session, low_team, [4.0] * 6, league_start)

    factor = compute_deep_completions_adjustment_factor(db_session, high_team.id, as_of=CUTOFF)
    assert factor is not None
    assert factor > 1.0


def test_deep_completions_factor_below_one_for_below_average_team(db_session):
    league_start = CUTOFF - timedelta(days=100)
    high_team = get_or_create_team(db_session, "Synth Deep High 2")
    low_team = get_or_create_team(db_session, "Synth Deep Low 2")
    db_session.flush()
    _seed_deep_values(db_session, high_team, [12.0] * 6, league_start)
    _seed_deep_values(db_session, low_team, [4.0] * 6, league_start)

    factor = compute_deep_completions_adjustment_factor(db_session, low_team.id, as_of=CUTOFF)
    assert factor is not None
    assert factor < 1.0


def test_deep_completions_factor_none_with_too_few_matches(db_session):
    team = get_or_create_team(db_session, "Synth Deep Sparse")
    db_session.flush()
    _seed_deep_values(db_session, team, [10.0, 10.0], CUTOFF - timedelta(days=30))
    assert 2 < MIN_MATCHES_FOR_FACTOR

    factor = compute_deep_completions_adjustment_factor(db_session, team.id, as_of=CUTOFF)
    assert factor is None
