"""Validates a qualitative `IntelligenceSignal` against observable
`TacticalFeature` data — the "quantitative layer validates the qualitative
layer, never the reverse" rule from ROADMAP.md item 6.

The check is deliberately generic and simple: compare a named feature's mean
in a window before the signal's asserted date to its mean in a window after,
and say whether the relative change clears a threshold. It does not know or
assume *which direction* a real tactical shift should move a given feature
(e.g. "more aggressive pressing" plausibly lowers PPDA, but this function
does not encode that domain claim) — that interpretation belongs to whoever
reads the `claim` text, a human or a future analysis step, not to this
function. What this function answers is narrower and more defensible: "did
this measurable number actually move around when the claim says it should
have," which is exactly what "the quantitative layer validates with
observable data" requires without smuggling in an assumption this project
hasn't verified.

Fails conservative like `reliability.py`: too few observations in either
window returns `supported=None` ("not judgeable"), never a guessed True/False.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.intelligence.signals import IntelligenceSignal, SignalCategory
from app.models.core import Team
from app.models.stats import TacticalFeature

MIN_OBSERVATIONS_PER_WINDOW = 3
DEFAULT_WINDOW_DAYS = 30
DEFAULT_RELATIVE_CHANGE_THRESHOLD = 0.10


@dataclass(frozen=True)
class ValidationResult:
    supported: bool | None  # None = not enough data to judge either way
    feature_name: str
    before_mean: float | None
    after_mean: float | None
    n_before: int
    n_after: int
    detail: str


def validate_tactical_shift_signal(
    db: Session,
    signal: IntelligenceSignal,
    feature_name: str,
    window_days: int = DEFAULT_WINDOW_DAYS,
    relative_change_threshold: float = DEFAULT_RELATIVE_CHANGE_THRESHOLD,
) -> ValidationResult:
    if signal.category != SignalCategory.TACTICAL_SHIFT:
        raise ValueError(
            f"validate_tactical_shift_signal only handles {SignalCategory.TACTICAL_SHIFT}, "
            f"got {signal.category}"
        )

    team = db.scalar(select(Team).where(Team.name == signal.team_name))
    if team is None:
        return ValidationResult(None, feature_name, None, None, 0, 0, f"no Team row for {signal.team_name!r}")

    before_start = signal.asserted_at - timedelta(days=window_days)
    after_end = signal.asserted_at + timedelta(days=window_days)

    before_values = list(
        db.scalars(
            select(TacticalFeature.value).where(
                TacticalFeature.team_id == team.id,
                TacticalFeature.feature_name == feature_name,
                TacticalFeature.as_of_date >= before_start,
                TacticalFeature.as_of_date < signal.asserted_at,
            )
        )
    )
    after_values = list(
        db.scalars(
            select(TacticalFeature.value).where(
                TacticalFeature.team_id == team.id,
                TacticalFeature.feature_name == feature_name,
                TacticalFeature.as_of_date >= signal.asserted_at,
                TacticalFeature.as_of_date < after_end,
            )
        )
    )

    before_mean = sum(before_values) / len(before_values) if before_values else None
    after_mean = sum(after_values) / len(after_values) if after_values else None

    if len(before_values) < MIN_OBSERVATIONS_PER_WINDOW or len(after_values) < MIN_OBSERVATIONS_PER_WINDOW:
        return ValidationResult(
            supported=None,
            feature_name=feature_name,
            before_mean=before_mean,
            after_mean=after_mean,
            n_before=len(before_values),
            n_after=len(after_values),
            detail=f"not enough observations to judge (need >= {MIN_OBSERVATIONS_PER_WINDOW} per window)",
        )

    if before_mean == 0:
        return ValidationResult(
            supported=None,
            feature_name=feature_name,
            before_mean=before_mean,
            after_mean=after_mean,
            n_before=len(before_values),
            n_after=len(after_values),
            detail="before_mean is 0 — relative change is undefined",
        )

    relative_change = (after_mean - before_mean) / before_mean
    supported = abs(relative_change) >= relative_change_threshold

    return ValidationResult(
        supported=supported,
        feature_name=feature_name,
        before_mean=before_mean,
        after_mean=after_mean,
        n_before=len(before_values),
        n_after=len(after_values),
        detail=f"relative change {relative_change:+.1%} (threshold {relative_change_threshold:.0%})",
    )
