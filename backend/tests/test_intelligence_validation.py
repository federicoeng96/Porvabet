"""Tests for validating a qualitative IntelligenceSignal against observable
TacticalFeature data (ROADMAP.md item 6) — SYNTHETIC teams/feature values."""

from datetime import date, timedelta

import pytest

from app.engine.intelligence.signals import IntelligenceSignal, SignalCategory
from app.engine.intelligence.validation import (
    MIN_OBSERVATIONS_PER_WINDOW,
    validate_tactical_shift_signal,
)
from app.ingestion.match_ingestion import get_or_create_team
from app.models.stats import TacticalFeature

ASSERTED_AT = date(2024, 1, 15)


def _seed_feature_values(db_session, team, feature_name, before_values, after_values):
    for day, v in enumerate(before_values):
        db_session.add(
            TacticalFeature(
                team_id=team.id,
                as_of_date=ASSERTED_AT - timedelta(days=10 + day),
                feature_name=feature_name,
                value=v,
                window_matches=1,
            )
        )
    for day, v in enumerate(after_values):
        db_session.add(
            TacticalFeature(
                team_id=team.id,
                as_of_date=ASSERTED_AT + timedelta(days=1 + day),
                feature_name=feature_name,
                value=v,
                window_matches=1,
            )
        )
    db_session.flush()


def _signal(team_name: str) -> IntelligenceSignal:
    return IntelligenceSignal(
        team_name=team_name,
        category=SignalCategory.TACTICAL_SHIFT,
        claim="More aggressive pressing since the new coach arrived",
        asserted_at=ASSERTED_AT,
        source="manual",
    )


def test_supported_when_feature_changes_beyond_threshold(db_session):
    team = get_or_create_team(db_session, "Synth Intel A")
    db_session.flush()
    _seed_feature_values(db_session, team, "ppda", before_values=[10.0, 10.0, 10.0, 10.0], after_values=[7.0, 7.0, 7.0, 7.0])

    result = validate_tactical_shift_signal(db_session, _signal("Synth Intel A"), feature_name="ppda")

    assert result.supported is True
    assert result.before_mean == pytest.approx(10.0)
    assert result.after_mean == pytest.approx(7.0)


def test_not_supported_when_feature_barely_changes(db_session):
    team = get_or_create_team(db_session, "Synth Intel B")
    db_session.flush()
    _seed_feature_values(db_session, team, "ppda", before_values=[10.0, 10.0, 10.0], after_values=[9.8, 9.9, 10.0])

    result = validate_tactical_shift_signal(db_session, _signal("Synth Intel B"), feature_name="ppda")

    assert result.supported is False


def test_not_estimable_with_too_few_observations(db_session):
    team = get_or_create_team(db_session, "Synth Intel C")
    db_session.flush()
    _seed_feature_values(db_session, team, "ppda", before_values=[10.0], after_values=[7.0])
    assert 1 < MIN_OBSERVATIONS_PER_WINDOW

    result = validate_tactical_shift_signal(db_session, _signal("Synth Intel C"), feature_name="ppda")

    assert result.supported is None
    assert "not enough observations" in result.detail


def test_unknown_team_returns_not_estimable(db_session):
    result = validate_tactical_shift_signal(db_session, _signal("No Such Team FC"), feature_name="ppda")
    assert result.supported is None
    assert "no Team row" in result.detail


def test_rejects_non_tactical_shift_category(db_session):
    get_or_create_team(db_session, "Synth Intel D")
    db_session.flush()
    bad_signal = IntelligenceSignal(
        team_name="Synth Intel D",
        category="NEWS_EVENT",  # not a real category yet — see signals.py docstring
        claim="irrelevant",
        asserted_at=ASSERTED_AT,
        source="manual",
    )
    with pytest.raises(ValueError):
        validate_tactical_shift_signal(db_session, bad_signal, feature_name="ppda")


def test_zero_before_mean_is_not_estimable(db_session):
    team = get_or_create_team(db_session, "Synth Intel E")
    db_session.flush()
    _seed_feature_values(db_session, team, "ppda", before_values=[0.0, 0.0, 0.0], after_values=[5.0, 5.0, 5.0])

    result = validate_tactical_shift_signal(db_session, _signal("Synth Intel E"), feature_name="ppda")

    assert result.supported is None
    assert "before_mean is 0" in result.detail
