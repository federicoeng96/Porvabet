import pytest

from app.engine.decision.fair_odds import fair_odds
from app.engine.decision.risk_score import WEIGHTS, RiskFactors, compute_risk_raw
from app.engine.decision.selection import Candidate, build_risk_ladder
from app.engine.decision.value import (
    ALERT_THRESHOLD_INTERESTING,
    ALERT_THRESHOLD_STRONG,
    classify_alert,
    discrepancy_pct,
    expected_value,
)
from app.models.enums import AlertLevel


def test_fair_odds_is_inverse_of_probability():
    assert fair_odds(0.5) == pytest.approx(2.0)
    assert fair_odds(0.25) == pytest.approx(4.0)


def test_fair_odds_rejects_invalid_probability():
    with pytest.raises(ValueError):
        fair_odds(0.0)
    with pytest.raises(ValueError):
        fair_odds(1.5)


def test_expected_value_breakeven_at_fair_odds():
    assert expected_value(0.5, 2.0) == pytest.approx(0.0)
    assert expected_value(0.5, 2.5) > 0
    assert expected_value(0.5, 1.5) < 0


def test_discrepancy_and_alert_thresholds():
    # Model says 60%, market implies 1/1.9 ≈ 52.6% -> ~14% relative discrepancy -> INTERESTING
    disc = discrepancy_pct(0.60, 1.9)
    assert ALERT_THRESHOLD_INTERESTING <= abs(disc) < ALERT_THRESHOLD_STRONG
    assert classify_alert(disc) == AlertLevel.INTERESTING

    disc_strong = discrepancy_pct(0.60, 1.3)  # market implies ~77%, model says 60% -> big gap
    assert classify_alert(disc_strong) == AlertLevel.STRONG

    disc_none = discrepancy_pct(0.50, 2.0)  # matches fair odds exactly
    assert classify_alert(disc_none) == AlertLevel.NONE


def test_risk_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_higher_uncertainty_increases_risk():
    base = RiskFactors(
        probability=0.5,
        bookmaker_odds=2.0,
        uncertainty=0.1,
        data_quality=0.9,
        model_reliability=0.8,
        prediction_stability=0.9,
        lineup_dependency=0.0,
    )
    riskier = RiskFactors(**{**base.__dict__, "uncertainty": 0.9})
    assert compute_risk_raw(riskier) > compute_risk_raw(base)


def test_lower_probability_increases_risk():
    base = RiskFactors(
        probability=0.7,
        bookmaker_odds=1.5,
        uncertainty=0.3,
        data_quality=0.9,
        model_reliability=0.8,
        prediction_stability=0.9,
        lineup_dependency=0.0,
    )
    riskier = RiskFactors(**{**base.__dict__, "probability": 0.2, "bookmaker_odds": 5.0})
    assert compute_risk_raw(riskier) > compute_risk_raw(base)


def test_compute_risk_raw_handles_no_real_quote_without_crashing():
    # bookmaker_odds=None (no real market price from any source — see
    # VERIFICATION_LOG.md) must never crash and never guess a substitute price;
    # the odds_magnitude weight is redistributed across the other factors
    # instead, so the score is still a valid, comparable [0, 1] risk.
    factors = RiskFactors(
        probability=0.5,
        bookmaker_odds=None,
        uncertainty=0.3,
        data_quality=0.9,
        model_reliability=0.8,
        prediction_stability=0.9,
        lineup_dependency=0.0,
    )
    score = compute_risk_raw(factors)
    assert 0.0 <= score <= 1.0

    # Same probability/uncertainty/etc — still riskier with lower probability,
    # exactly like the priced case, since redistributing weight doesn't disable
    # the other factors.
    riskier = RiskFactors(**{**factors.__dict__, "probability": 0.2})
    assert compute_risk_raw(riskier) > compute_risk_raw(factors)


def test_compute_risk_raw_no_quote_never_equals_an_arbitrary_priced_value():
    # Never a fabricated stand-in price: None must not silently behave like
    # some specific decimal odds (e.g. fair odds == 1/probability), which would
    # just be a hidden guess wearing a different name.
    probability = 0.4
    priced_at_fair_odds = RiskFactors(
        probability=probability,
        bookmaker_odds=1.0 / probability,
        uncertainty=0.3,
        data_quality=0.9,
        model_reliability=0.8,
        prediction_stability=0.9,
        lineup_dependency=0.0,
    )
    no_quote = RiskFactors(**{**priced_at_fair_odds.__dict__, "bookmaker_odds": None})
    assert compute_risk_raw(no_quote) != pytest.approx(compute_risk_raw(priced_at_fair_odds))


def _candidate(key, category, label, outcome, prob, odds, uncertainty=0.3) -> Candidate:
    factors = RiskFactors(
        probability=prob,
        bookmaker_odds=odds,
        uncertainty=uncertainty,
        data_quality=0.8,
        model_reliability=0.7,
        prediction_stability=0.9,
        lineup_dependency=0.0,
    )
    return Candidate(key, category, label, outcome, prob, odds, 1 / prob, factors)


def test_build_risk_ladder_produces_all_ten_levels():
    candidates = [
        _candidate("MATCH_RESULT:HOME", "MATCH_RESULT", "1X2", "HOME", 0.55, 1.75),
        _candidate("MATCH_RESULT:DRAW", "MATCH_RESULT", "1X2", "DRAW", 0.25, 3.6),
        _candidate("MATCH_RESULT:AWAY", "MATCH_RESULT", "1X2", "AWAY", 0.20, 4.5),
        _candidate("TOTAL_GOALS:OVER", "TOTAL_GOALS", "O/U 2.5", "OVER", 0.52, 1.9),
        _candidate("TOTAL_GOALS:UNDER", "TOTAL_GOALS", "O/U 2.5", "UNDER", 0.48, 2.0),
        _candidate("BTTS:YES", "BOTH_TEAMS_TO_SCORE", "BTTS", "YES", 0.58, 1.7),
        _candidate("BTTS:NO", "BOTH_TEAMS_TO_SCORE", "BTTS", "NO", 0.42, 2.3),
    ]
    ladder = build_risk_ladder(candidates)
    assert [lvl.risk_level for lvl in ladder] == list(range(1, 11))
    for level in ladder:
        assert len(level.alternatives) == 2
        # alternatives must never repeat the main pick
        assert level.main.candidate.market_outcome_key not in {
            a.candidate.market_outcome_key for a in level.alternatives
        }


def test_risk_ladder_is_monotonic_in_risk_raw():
    candidates = [
        _candidate("MATCH_RESULT:HOME", "MATCH_RESULT", "1X2", "HOME", 0.55, 1.75),
        _candidate("MATCH_RESULT:DRAW", "MATCH_RESULT", "1X2", "DRAW", 0.25, 3.6),
        _candidate("MATCH_RESULT:AWAY", "MATCH_RESULT", "1X2", "AWAY", 0.20, 4.5),
        _candidate("TOTAL_GOALS:OVER", "TOTAL_GOALS", "O/U 2.5", "OVER", 0.52, 1.9),
        _candidate("TOTAL_GOALS:UNDER", "TOTAL_GOALS", "O/U 2.5", "UNDER", 0.48, 2.0),
        _candidate("BTTS:YES", "BOTH_TEAMS_TO_SCORE", "BTTS", "YES", 0.58, 1.7),
        _candidate("BTTS:NO", "BOTH_TEAMS_TO_SCORE", "BTTS", "NO", 0.42, 2.3),
    ]
    ladder = build_risk_ladder(candidates)
    risk_raws = [lvl.main.risk_raw for lvl in ladder]
    assert risk_raws == sorted(risk_raws)


def test_build_risk_ladder_rejects_empty_input():
    with pytest.raises(ValueError):
        build_risk_ladder([])


def _nd_candidate(key, category, label, outcome, prob, uncertainty=0.3) -> Candidate:
    """A candidate with no real quote anywhere — bookmaker_odds/value stay None
    ("n/d"), same construction analysis_runner.py now uses when no configured
    odds source has a liquid quote for this outcome."""
    factors = RiskFactors(
        probability=prob,
        bookmaker_odds=None,
        uncertainty=uncertainty,
        data_quality=0.8,
        model_reliability=0.7,
        prediction_stability=0.9,
        lineup_dependency=0.0,
    )
    return Candidate(key, category, label, outcome, prob, None, 1 / prob, factors)


def test_build_risk_ladder_works_when_every_candidate_is_nd():
    # The real scenario found in VERIFICATION_LOG.md: Betfair unavailable and no
    # historical closing odds, so literally no market anywhere has a quote. The
    # ladder must still be fully built (10 levels), never raise, with every
    # selection's value explicitly None rather than a fabricated number.
    candidates = [
        _nd_candidate("MATCH_RESULT:HOME", "MATCH_RESULT", "1X2", "HOME", 0.55),
        _nd_candidate("MATCH_RESULT:DRAW", "MATCH_RESULT", "1X2", "DRAW", 0.25),
        _nd_candidate("MATCH_RESULT:AWAY", "MATCH_RESULT", "1X2", "AWAY", 0.20),
        _nd_candidate("TOTAL_GOALS:OVER", "TOTAL_GOALS", "O/U 2.5", "OVER", 0.52),
        _nd_candidate("TOTAL_GOALS:UNDER", "TOTAL_GOALS", "O/U 2.5", "UNDER", 0.48),
    ]
    ladder = build_risk_ladder(candidates)
    assert [lvl.risk_level for lvl in ladder] == list(range(1, 11))
    for level in ladder:
        assert level.main.value is None
        assert level.main.candidate.bookmaker_odds is None
        for alt in level.alternatives:
            assert alt.value is None
            assert alt.candidate.bookmaker_odds is None


def test_build_risk_ladder_mixes_priced_and_nd_candidates():
    # The "some markets missing a quote" case, generalized: priced candidates
    # are preferred as main picks over n/d ones when both are otherwise
    # eligible (tie-break), but an n/d candidate is still a fully valid
    # selection, never dropped from the ladder.
    candidates = [
        _candidate("MATCH_RESULT:HOME", "MATCH_RESULT", "1X2", "HOME", 0.55, 1.75),
        _candidate("MATCH_RESULT:DRAW", "MATCH_RESULT", "1X2", "DRAW", 0.25, 3.6),
        _candidate("MATCH_RESULT:AWAY", "MATCH_RESULT", "1X2", "AWAY", 0.20, 4.5),
        _nd_candidate("TOTAL_GOALS:OVER", "TOTAL_GOALS", "O/U 2.5", "OVER", 0.52),
        _nd_candidate("TOTAL_GOALS:UNDER", "TOTAL_GOALS", "O/U 2.5", "UNDER", 0.48),
    ]
    ladder = build_risk_ladder(candidates)
    assert [lvl.risk_level for lvl in ladder] == list(range(1, 11))
    all_selections = [lvl.main for lvl in ladder] + [a for lvl in ladder for a in lvl.alternatives]
    nd_selections = [s for s in all_selections if s.candidate.bookmaker_odds is None]
    priced_selections = [s for s in all_selections if s.candidate.bookmaker_odds is not None]
    assert nd_selections and priced_selections  # both kinds actually appear
    for s in nd_selections:
        assert s.value is None
    for s in priced_selections:
        assert s.value is not None


def test_player_market_with_lineup_conflict_never_main_when_alternative_exists():
    conflicted_player = Candidate(
        "PLAYER_SHOTS:OVER",
        "PLAYER_SHOTS",
        "Player shots O/U",
        "OVER",
        0.9,  # deliberately very favorable-looking, to prove it's excluded on principle
        1.2,
        1 / 0.9,
        RiskFactors(0.9, 1.2, 0.1, 0.9, 0.9, 0.9, lineup_dependency=1.0),
        is_player_market=True,
        lineup_conflict=True,
    )
    safe_alternative = _candidate("TOTAL_GOALS:OVER", "TOTAL_GOALS", "O/U 2.5", "OVER", 0.52, 1.9)
    candidates = [conflicted_player, safe_alternative]
    ladder = build_risk_ladder(candidates)
    mains = {lvl.main.candidate.market_outcome_key for lvl in ladder}
    assert "PLAYER_SHOTS:OVER" not in mains
