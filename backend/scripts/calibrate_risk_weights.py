"""Calibrate `risk_score.WEIGHTS` against real backtest data — the one item
BACKTEST_SPEC.md's "Cosa manca" still listed as open ("resta aperta... la
ricalibrazione dei pesi di risk_score.WEIGHTS - nessuna analisi tentata
finora su quel punto specifico").

**Structural finding this script exists to act on** (verified directly with
a dedicated test before writing this script — see CHANGELOG.md — not just
reasoned about): in the walk-forward backtest, `uncertainty`, `data_quality`,
`model_reliability`, `prediction_stability` and `lineup_dependency` are all
IDENTICAL across every candidate built for the same match (see
`app/backtest/runner.py::_build_candidates` and BACKTEST_SPEC.md
"Approssimazioni dei fattori di rischio" — this is a deliberate, documented
simplification, not an oversight). `build_risk_ladder` ranks candidates only
relative to OTHER candidates of the SAME match, and adding a per-match
constant (or scaling every candidate's score by the same positive factor)
never changes a ranking — so no per-risk-level metric this backtest can
produce is capable of telling those 5 weights apart from any other value:
they are structurally unidentifiable from this data, not merely "not yet
tested". Reweighting them here would be numerology, not calibration, so this
script leaves them untouched and says so plainly in its output.

Only `improbability` and `odds_magnitude` vary candidate-to-candidate within
a match (from `probability`/`bookmaker_odds`), so only the SPLIT between
those two survives contact with this data — that split is the one degree of
freedom this script actually tunes, holding their combined mass (0.40,
matching the current `WEIGHTS`) and every other weight fixed.

Uses `generate_match_candidates` (the expensive, weight-independent half of
`run_walk_forward_backtest` — one Dixon-Coles walk-forward fit per
competition, cached) and re-scores it cheaply against a grid of
improbability:odds_magnitude splits via `resolve_match_candidates`, so the
whole grid costs one backtest run per competition, not one per grid point.

Run against the dev DB already populated by `scripts/ingest_football_data.py`
(same real EPL + Serie A data as `scripts/persist_backtest_results.py`).
"""

from app.backtest.data_loading import load_goal_records, load_season_matches
from app.backtest.metrics import BetRecord, segment
from app.backtest.runner import (
    REFIT_BATCH_DAYS,
    generate_match_candidates,
    resolve_match_candidates,
)
from app.db.session import SessionLocal
from app.engine.decision.risk_score import WEIGHTS

COMPETITIONS = ["EPL", "SERIE_A"]

# Fraction of the combined (improbability + odds_magnitude) mass assigned to
# odds_magnitude. 0.25 is the current production split (0.10 / 0.40).
GRID_ODDS_FRACTION = [0.0, 0.10, 0.25, 0.50, 0.75, 1.0]

MOVABLE_MASS = WEIGHTS["improbability"] + WEIGHTS["odds_magnitude"]
_OTHER_WEIGHTS_SUM = sum(w for k, w in WEIGHTS.items() if k not in ("improbability", "odds_magnitude"))
assert abs(_OTHER_WEIGHTS_SUM + MOVABLE_MASS - 1.0) < 1e-9


def make_weights(odds_fraction: float) -> dict[str, float]:
    w = dict(WEIGHTS)
    w["odds_magnitude"] = MOVABLE_MASS * odds_fraction
    w["improbability"] = MOVABLE_MASS * (1.0 - odds_fraction)
    assert abs(sum(w.values()) - 1.0) < 1e-9
    return w


def to_bet_records(resolved) -> list[BetRecord]:
    return [
        BetRecord(r.probability, r.bookmaker_odds, r.won, r.risk_level, r.market_category, r.is_home_selection)
        for r in resolved
    ]


def monotonicity_score(level_hit_rates: dict[int, float]) -> tuple[int, int]:
    """(concordant, total) pairs among the 10 risk levels where a lower risk
    level has a hit rate >= a higher one (the direction the risk ladder is
    supposed to guarantee — see risk_score.py module docstring). Ties count
    as concordant (expected: with 5 raw candidates per match mapped into 10
    levels, adjacent levels are frequently the exact same candidate — see
    BACKTEST_SPEC.md's own 1-2/3-4/.../9-10 pairing in its reported table)."""
    levels = sorted(level_hit_rates)
    concordant = 0
    total = 0
    for i in range(len(levels)):
        for j in range(i + 1, len(levels)):
            total += 1
            if level_hit_rates[levels[i]] >= level_hit_rates[levels[j]]:
                concordant += 1
    return concordant, total


def main() -> None:
    db = SessionLocal()
    cached: dict[str, list] = {}
    for comp in COMPETITIONS:
        matches = load_season_matches(db, comp)
        records = load_goal_records(db, comp, matches)
        print(f"{comp}: {len(records)} matches loaded, running walk-forward candidate generation "
              f"(refit_batch_days={REFIT_BATCH_DAYS}, one-time cost)...", flush=True)
        cached[comp] = generate_match_candidates(records, refit_batch_days=REFIT_BATCH_DAYS)
        print(f"{comp}: {len(cached[comp])} matches with candidates cached.", flush=True)
    db.close()

    print()
    print("=" * 100)
    print("improbability:odds_magnitude split  |  per-competition risk-level monotonicity + hit-rate table")
    print("=" * 100)

    for frac in GRID_ODDS_FRACTION:
        w = make_weights(frac)
        marker = "  <-- current production split" if abs(frac - 0.25) < 1e-9 else ""
        print(f"\nodds_magnitude fraction = {frac:.2f}  "
              f"(improbability={w['improbability']:.3f}, odds_magnitude={w['odds_magnitude']:.3f}){marker}")
        for comp in COMPETITIONS:
            resolved = resolve_match_candidates(cached[comp], weights=w)
            bets = to_bet_records(resolved)
            seg = segment(bets, key=lambda b: b.risk_level)
            level_hit_rates = {int(level): stats["hit_rate"] for level, stats in seg.items() if stats["hit_rate"] is not None}
            concordant, total = monotonicity_score(level_hit_rates)
            table = ", ".join(f"L{lvl}:{level_hit_rates[lvl]:.1%}" for lvl in sorted(level_hit_rates))
            print(f"  {comp:8s} n={len(bets):6d}  monotonic pairs {concordant:2d}/{total:2d}  |  {table}")


if __name__ == "__main__":
    main()
