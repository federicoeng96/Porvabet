"""Corrections to a statistical model's raw expected counts, derived from
real `TacticalFeature` data (MODEL_SPEC.md / ROADMAP.md — "collega le
TacticalFeature al Decision Engine"). Two independent corrections live here:
`compute_xg_adjustment_factor` for Dixon-Coles' goal expectation, and
`compute_deep_completions_adjustment_factor` for `PoissonCountModel`'s corner
expectation — both feed into the same `apply_tactical_adjustment`.

**The idea, stated precisely, not just asserted**: Dixon-Coles fits
attack/defense strength from actual goals scored/conceded. Actual goals are
noisy over a season — a team can systematically create better chances than
its raw scoreline shows (finishing below its process, "unlucky") or worse
("overperforming", riding a hot streak) — and expected goals (xG) is exactly
the standard sports-analytics measure of that underlying chance quality,
independent of finishing variance. A team whose xG has run persistently above
its actual goals over its most recent matches is, by this specific and
well-understood mechanism (not a vague "the model should use more data"
claim), plausibly a bit more dangerous going forward than its raw scoreline
alone implies — and vice versa.

**Coverage boundary, explicit**: `TacticalFeature` xG rows exist only for
EPL+Serie A 2023/24 (see ROADMAP.md item 5) — real data from understat.com,
not fabricated. `compute_xg_adjustment_factor` returns `None`, not a guessed
1.0, whenever a team lacks enough *prior* xG observations for the date being
predicted — the caller (see `apply_tactical_adjustment`) must leave the
Dixon-Coles expectation unmodified in that case, never apply a default
correction to a team/period this data doesn't actually cover.

**No-leakage**: every xG/goals pair used to compute a team's factor for a
prediction dated `as_of` must have `TacticalFeature.as_of_date < as_of` — the
same "never see the future" rule the rest of this project enforces.

Whether this adjustment is actually applied by default is a real backtest
question, not assumed here — see BACKTEST_SPEC.md "xG-adjusted Dixon-Coles"
for the before/after comparison and the resulting decision.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.stats import TacticalFeature

MIN_MATCHES_FOR_FACTOR = 5
# A safety bound on the correction itself, not a tuned parameter: caps how far
# a (necessarily noisy, single-season, <=38-match) xG sample can move the
# model's own fitted expectation, so a small, streaky sample can't produce an
# implausible swing. Chosen as a symmetric +/-33% band in linear space
# (1/1.33 ~= 0.75), a generous but bounded range — not fit to backtest
# results (see BACKTEST_SPEC.md for why this matters to say explicitly).
FACTOR_CLIP_RANGE = (0.75, 1.33)


def compute_xg_adjustment_factor(
    db: Session, team_id: int, as_of: date, min_matches: int = MIN_MATCHES_FOR_FACTOR
) -> float | None:
    """Ratio of a team's mean xG to its mean actual goals scored, over all
    matches strictly before `as_of` for which a `TacticalFeature` "xg" row
    exists for this team. `None` when fewer than `min_matches` such matches
    exist (not enough signal to trust) or when actual goals average to zero
    (ratio undefined) — never a guessed factor."""
    xg_rows = db.execute(
        select(TacticalFeature.as_of_date, TacticalFeature.value).where(
            TacticalFeature.team_id == team_id,
            TacticalFeature.feature_name == "xg",
            TacticalFeature.as_of_date < as_of,
        )
    ).all()
    if len(xg_rows) < min_matches:
        return None

    total_xg = 0.0
    total_actual = 0.0
    matched = 0
    for match_date, xg_value in xg_rows:
        actual_goals = _actual_goals_for_team_on_date(db, team_id, match_date)
        if actual_goals is None:
            continue  # no Match row for this date (shouldn't normally happen, but never guess)
        total_xg += xg_value
        total_actual += actual_goals
        matched += 1

    if matched < min_matches or total_actual == 0:
        return None

    factor = total_xg / total_actual
    low, high = FACTOR_CLIP_RANGE
    return max(low, min(high, factor))


def _actual_goals_for_team_on_date(db: Session, team_id: int, match_date: date) -> int | None:
    # Filtered in Python (not SQL) on `kickoff_utc.date() == match_date`: a
    # tz-aware datetime column has no portable single-comparison "same
    # calendar date" expression across dialects, and a team plays at most one
    # match per day, so this is not a meaningful cost.
    candidates = db.scalars(
        select(Match).where(
            (Match.home_team_id == team_id) | (Match.away_team_id == team_id),
            Match.kickoff_utc >= match_date,
            Match.kickoff_utc < match_date + timedelta(days=2),
        )
    ).all()
    match = next((m for m in candidates if m.kickoff_utc.date() == match_date), None)
    if match is None or match.home_goals_ft is None or match.away_goals_ft is None:
        return None
    return match.home_goals_ft if match.home_team_id == team_id else match.away_goals_ft


def apply_tactical_adjustment(
    lam: float, mu: float, home_factor: float | None, away_factor: float | None
) -> tuple[float, float]:
    """Multiplies a model's raw expected count (Dixon-Coles' goals or
    PoissonCountModel's corners) by each team's adjustment factor, leaving a
    side unmodified when its factor is `None` (not enough data for that
    team/period — see module docstring)."""
    adjusted_lam = lam * home_factor if home_factor is not None else lam
    adjusted_mu = mu * away_factor if away_factor is not None else mu
    return adjusted_lam, adjusted_mu


def compute_deep_completions_adjustment_factor(
    db: Session, team_id: int, as_of: date, min_matches: int = MIN_MATCHES_FOR_FACTOR
) -> float | None:
    """Correction factor for `PoissonCountModel`'s corner-count expectation,
    from `TacticalFeature` "deep" (deep completions — passes completed near
    the opponent's goal). Checked against real data before building this (see
    BACKTEST_SPEC.md "PPDA/deep completions vs corners"): deep completions
    correlate with actual corners won (Pearson r=+0.45 on the 2023/24
    EPL+Serie A data this project has), a real signal, not assumed.

    Ratio of this team's mean deep completions (strictly prior matches only)
    to the *league-wide* mean deep completions over the same prior-only
    window (mixing EPL+Serie A — a simplification, not per-competition; see
    BACKTEST_SPEC.md for why this was not refined further) — a team creating
    20% more deep attacking buildup than a typical team recently is
    hypothesized to win proportionally more corners. `None` (never a guessed
    1.0) when either this team or the league-wide baseline has fewer than
    `min_matches` prior observations, or the league mean is zero.
    """
    team_values = list(
        db.scalars(
            select(TacticalFeature.value).where(
                TacticalFeature.team_id == team_id,
                TacticalFeature.feature_name == "deep",
                TacticalFeature.as_of_date < as_of,
            )
        )
    )
    if len(team_values) < min_matches:
        return None

    league_values = list(
        db.scalars(
            select(TacticalFeature.value).where(
                TacticalFeature.feature_name == "deep",
                TacticalFeature.as_of_date < as_of,
            )
        )
    )
    if len(league_values) < min_matches:
        return None

    league_mean = sum(league_values) / len(league_values)
    if league_mean == 0:
        return None

    team_mean = sum(team_values) / len(team_values)
    factor = team_mean / league_mean
    low, high = FACTOR_CLIP_RANGE
    return max(low, min(high, factor))
