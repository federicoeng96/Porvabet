"""Reconciles multiple probable-lineup sources into a confidence signal.

Per the brief: an official lineup always wins outright; among probable lineups,
agreement between sources raises confidence, disagreement lowers it and must
block a dependent player-market selection from being the main pick (enforced in
selection.py via `Candidate.lineup_conflict`).
"""

from dataclasses import dataclass

from app.models.enums import LineupConfidence
from app.providers.base.dto import LineupProjectionRecord


@dataclass(frozen=True)
class LineupReconciliation:
    confidence_level: LineupConfidence
    confidence_score: float  # 0..1, feeds RiskFactors.data_quality for lineup-dependent markets
    is_conflicting: bool
    agreed_starting_players: frozenset[str]
    disputed_players: frozenset[str]


def reconcile(
    official: LineupProjectionRecord | None,
    probable_sources: list[LineupProjectionRecord],
) -> LineupReconciliation:
    if official is not None:
        players = frozenset(official.player_names_starting)
        return LineupReconciliation(
            confidence_level=LineupConfidence.OFFICIAL,
            confidence_score=1.0,
            is_conflicting=False,
            agreed_starting_players=players,
            disputed_players=frozenset(),
        )

    if not probable_sources:
        return LineupReconciliation(
            confidence_level=LineupConfidence.UNKNOWN,
            confidence_score=0.0,
            is_conflicting=False,
            agreed_starting_players=frozenset(),
            disputed_players=frozenset(),
        )

    if len(probable_sources) == 1:
        players = frozenset(probable_sources[0].player_names_starting)
        return LineupReconciliation(
            confidence_level=LineupConfidence.PROBABLE_CONFLICTING,  # single unconfirmed source
            confidence_score=0.45,
            is_conflicting=False,
            agreed_starting_players=players,
            disputed_players=frozenset(),
        )

    player_sets = [frozenset(s.player_names_starting) for s in probable_sources]
    agreed = frozenset.intersection(*player_sets)
    all_mentioned = frozenset.union(*player_sets)
    disputed = all_mentioned - agreed

    if not disputed:
        return LineupReconciliation(
            confidence_level=LineupConfidence.PROBABLE_CONFIRMED,
            confidence_score=0.85,
            is_conflicting=False,
            agreed_starting_players=agreed,
            disputed_players=frozenset(),
        )

    return LineupReconciliation(
        confidence_level=LineupConfidence.PROBABLE_CONFLICTING,
        confidence_score=0.35,
        is_conflicting=True,
        agreed_starting_players=agreed,
        disputed_players=disputed,
    )
