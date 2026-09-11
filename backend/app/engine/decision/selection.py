"""Builds the 10-level risk ladder (1 main + 2 alternatives per level) for a match.

Important, honest limitation of the current vertical slice: with only the
MATCH_RESULT / DOUBLE_CHANCE / TOTAL_GOALS / BOTH_TEAMS_TO_SCORE markets
implemented (see ROADMAP.md — corners/cards/player-props markets need dedicated
models not yet built), a single match typically has on the order of 10 candidate
outcomes, not the 30 distinct slots that 10 risk levels x 3 selections would need
to fill without any reuse. This module still produces a full 1..10 ladder (never
silently drops a level), but is upfront that in this slice the same underlying
selection can legitimately be the best fit for more than one adjacent risk level;
that stops being a meaningful limitation once more markets are added, which is
exactly the roadmap-tracked next step, not a workaround to hide.
"""

from dataclasses import dataclass

from app.engine.decision.risk_score import RiskFactors, compute_risk_raw
from app.engine.decision.value import expected_value


@dataclass(frozen=True)
class Candidate:
    market_outcome_key: str  # unique key, e.g. "MATCH_RESULT:HOME"
    market_category: str
    market_label: str
    outcome_label: str
    probability: float
    bookmaker_odds: float
    fair_odds_value: float
    risk_factors: RiskFactors
    is_player_market: bool = False
    lineup_conflict: bool = False


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    risk_raw: float
    value: float


@dataclass(frozen=True)
class RiskLevelSelection:
    risk_level: int
    main: ScoredCandidate
    alternatives: tuple[ScoredCandidate, ScoredCandidate] | tuple[ScoredCandidate] | tuple[()]
    rationale: str


def score_candidates(candidates: list[Candidate]) -> list[ScoredCandidate]:
    scored = [
        ScoredCandidate(
            candidate=c,
            risk_raw=compute_risk_raw(c.risk_factors),
            value=expected_value(c.probability, c.bookmaker_odds),
        )
        for c in candidates
    ]
    return sorted(scored, key=lambda s: s.risk_raw)


def _assign_risk_levels(scored: list[ScoredCandidate]) -> dict[int, list[ScoredCandidate]]:
    """Rank-based bucketing into 10 levels: level 1 = lowest risk_raw decile."""
    n = len(scored)
    buckets: dict[int, list[ScoredCandidate]] = {level: [] for level in range(1, 11)}
    for rank, item in enumerate(scored):
        level = min(10, int(rank * 10 / n) + 1)
        buckets[level].append(item)
    return buckets


def build_risk_ladder(candidates: list[Candidate]) -> list[RiskLevelSelection]:
    if not candidates:
        raise ValueError("Cannot build a risk ladder with zero candidates")

    scored = score_candidates(candidates)
    buckets = _assign_risk_levels(scored)

    # Player-market selections can never be the main pick for a level while their
    # backing lineup is in conflict between sources (see MODEL_SPEC.md "Lineup
    # conflict handling") — a non-player alternative must always exist.
    def is_eligible_main(item: ScoredCandidate) -> bool:
        return not (item.candidate.is_player_market and item.candidate.lineup_conflict)

    ladder: list[RiskLevelSelection] = []
    used_market_keys_as_main: set[str] = set()

    any_eligible_exists = any(is_eligible_main(c) for c in scored)

    for level in range(1, 11):
        bucket = buckets[level]
        pool = bucket if bucket else _nearest_non_empty_bucket(buckets, level)

        eligible = [c for c in pool if is_eligible_main(c)]
        if not eligible:
            # The local risk bucket has no eligible (non-conflicted) candidate —
            # widen the search to the whole candidate set rather than silently
            # falling back to an ineligible one, since the "always keep a safe
            # alternative" guarantee must hold globally, not just per-bucket.
            if any_eligible_exists:
                eligible = sorted(
                    (c for c in scored if is_eligible_main(c)),
                    key=lambda c: abs(c.risk_raw - pool[0].risk_raw),
                )
            else:
                eligible = pool  # no eligible candidate exists anywhere — degrade gracefully
        # Prefer a market not already used as another level's main pick, then
        # by highest value, then by lowest uncertainty (a tighter estimate wins
        # among equally-valued options).
        fresh = [c for c in eligible if c.candidate.market_outcome_key not in used_market_keys_as_main]
        main_pool = fresh or eligible
        main = max(
            main_pool,
            key=lambda c: (round(c.value, 6), -c.candidate.risk_factors.uncertainty),
        )
        used_market_keys_as_main.add(main.candidate.market_outcome_key)

        alternatives = _pick_alternatives(scored, exclude_key=main.candidate.market_outcome_key, near=main)

        ladder.append(
            RiskLevelSelection(
                risk_level=level,
                main=main,
                alternatives=alternatives,
                rationale=_rationale(main),
            )
        )
    return ladder


def _nearest_non_empty_bucket(
    buckets: dict[int, list[ScoredCandidate]], level: int
) -> list[ScoredCandidate]:
    for distance in range(1, 10):
        for neighbor in (level - distance, level + distance):
            if 1 <= neighbor <= 10 and buckets[neighbor]:
                return buckets[neighbor]
    raise RuntimeError("No candidates available in any risk bucket")


def _pick_alternatives(
    all_scored: list[ScoredCandidate], exclude_key: str, near: ScoredCandidate
) -> tuple[ScoredCandidate, ...]:
    others = [c for c in all_scored if c.candidate.market_outcome_key != exclude_key]
    others.sort(key=lambda c: abs(c.risk_raw - near.risk_raw))
    picked: list[ScoredCandidate] = []
    seen_categories: set[str] = {near.candidate.market_category}
    for c in others:
        if len(picked) == 2:
            break
        if c.candidate.market_category in seen_categories and len(others) > 2:
            continue  # prefer variety across markets when the pool allows it
        picked.append(c)
        seen_categories.add(c.candidate.market_category)
    if len(picked) < 2:
        for c in others:
            if len(picked) == 2:
                break
            if c not in picked:
                picked.append(c)
    return tuple(picked[:2])


def _rationale(item: ScoredCandidate) -> str:
    c = item.candidate
    return (
        f"{c.market_label} — {c.outcome_label}: probabilità stimata {c.probability:.1%}, "
        f"quota {c.bookmaker_odds:.2f}, valore atteso {item.value:+.1%}, "
        f"incertezza {c.risk_factors.uncertainty:.0%}, qualità dati {c.risk_factors.data_quality:.0%}."
    )
