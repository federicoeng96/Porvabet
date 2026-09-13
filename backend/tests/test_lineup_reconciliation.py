"""Tests for app.engine.decision.lineup_reconciliation.reconcile().

Covers all 5 branches described in the module's own docstring: official
lineup present, no probable sources at all, exactly one probable source,
multiple probable sources fully agreeing, and multiple probable sources
disagreeing (which must set is_conflicting=True).
"""

from datetime import UTC, datetime

from app.engine.decision.lineup_reconciliation import reconcile
from app.models.enums import LineupConfidence
from app.providers.base.dto import LineupProjectionRecord

NOW = datetime(2025, 8, 1, 12, 0, tzinfo=UTC)


def _record(players, source_key="src", is_official=False):
    return LineupProjectionRecord(
        team_name="Roma",
        player_names_starting=players,
        formation="4-3-3",
        is_official=is_official,
        published_at=NOW,
        source_key=source_key,
    )


def test_official_lineup_always_wins_outright():
    official = _record(["A", "B", "C"], source_key="official", is_official=True)
    probable = [_record(["A", "X", "Y"], source_key="probable_source")]

    result = reconcile(official, probable)

    assert result.confidence_level == LineupConfidence.OFFICIAL
    assert result.confidence_score == 1.0
    assert result.is_conflicting is False
    assert result.agreed_starting_players == frozenset({"A", "B", "C"})
    assert result.disputed_players == frozenset()


def test_no_official_and_no_probable_sources_is_unknown():
    result = reconcile(None, [])

    assert result.confidence_level == LineupConfidence.UNKNOWN
    assert result.confidence_score == 0.0
    assert result.is_conflicting is False
    assert result.agreed_starting_players == frozenset()
    assert result.disputed_players == frozenset()


def test_single_probable_source_is_conflicting_confidence_but_not_marked_conflicting():
    probable = [_record(["A", "B"], source_key="sosfanta")]

    result = reconcile(None, probable)

    assert result.confidence_level == LineupConfidence.PROBABLE_CONFLICTING
    assert result.confidence_score == 0.45
    assert result.is_conflicting is False
    assert result.agreed_starting_players == frozenset({"A", "B"})
    assert result.disputed_players == frozenset()


def test_multiple_probable_sources_fully_agreeing_is_confirmed():
    probable = [
        _record(["A", "B", "C"], source_key="sosfanta"),
        _record(["A", "B", "C"], source_key="gazzetta"),
    ]

    result = reconcile(None, probable)

    assert result.confidence_level == LineupConfidence.PROBABLE_CONFIRMED
    assert result.confidence_score == 0.85
    assert result.is_conflicting is False
    assert result.agreed_starting_players == frozenset({"A", "B", "C"})
    assert result.disputed_players == frozenset()


def test_multiple_probable_sources_disagreeing_is_conflicting():
    probable = [
        _record(["A", "B", "C"], source_key="sosfanta"),
        _record(["A", "B", "X"], source_key="gazzetta"),
    ]

    result = reconcile(None, probable)

    assert result.confidence_level == LineupConfidence.PROBABLE_CONFLICTING
    assert result.confidence_score == 0.35
    assert result.is_conflicting is True
    assert result.agreed_starting_players == frozenset({"A", "B"})
    assert result.disputed_players == frozenset({"C", "X"})


def test_three_probable_sources_partial_agreement():
    probable = [
        _record(["A", "B", "C"], source_key="sosfanta"),
        _record(["A", "B", "D"], source_key="gazzetta"),
        _record(["A", "B", "C"], source_key="corriere"),
    ]

    result = reconcile(None, probable)

    assert result.confidence_level == LineupConfidence.PROBABLE_CONFLICTING
    assert result.is_conflicting is True
    assert result.agreed_starting_players == frozenset({"A", "B"})
    assert result.disputed_players == frozenset({"C", "D"})
