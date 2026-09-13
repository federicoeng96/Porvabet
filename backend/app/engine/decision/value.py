"""Value/edge estimation and alert thresholds.

`value` uses the standard sports-betting EV formula `p * odds - 1` (expected
profit per unit staked, assuming `p` is correct) rather than a more exotic
measure, because it is the simplest quantity that is both directly interpretable
("expected return per euro staked") and the one every downstream consumer
(risk engine, alert popover, backtest ROI/yield) already needs in that form —
introducing a different discrepancy measure would mean maintaining two
incompatible notions of "how good is this bet" across the codebase.

`discrepancy_pct` is a separate, purely descriptive measure used for the alert
threshold, expressed relative to the market's own implied probability (not an
absolute probability-point difference), because a 5-point gap means something
very different for a 90% shot than for a 20% shot — see MODEL_SPEC.md.
"""

from app.models.enums import AlertLevel

# Calibrated against the real 10-season walk-forward backtest (74,100 resolved
# predictions, both leagues, all markets/risk-levels — see BACKTEST_SPEC.md
# "Calibrazione soglie alert su dati reali"), not provisional guesses anymore.
#
# The real finding inverts the assumption baked into the original brief: a
# LARGER model-vs-market discrepancy does not mean the model is more likely to
# be right (an "opportunity") — bucketed ROI gets steadily WORSE as
# |discrepancy| grows (-3.0% at 0-5%, -2.7% at 15-20%, -7.5% at 20-30%,
# -14.6% at 30%+), and hit rate falls from 39.5% to 22.2% over the same
# range. STRONG is therefore best read as "this model disagrees a lot with
# the market here, which historically means the model is more often wrong,
# not that the market is mispriced" — a caution flag, not a value signal (see
# `classify_alert`'s docstring and the frontend copy this drives).
#
# ALERT_THRESHOLD_STRONG moved from 0.15 to 0.20: the bucketed data shows
# 10-15%/15-20% behaving similarly (~-2.7% to -2.9% ROI) while 20%+ is where
# performance clearly drops off a cliff (-7.5%, then -14.6%) — 0.20 is where
# that real breakpoint sits, not an arbitrary round number.
# ALERT_THRESHOLD_INTERESTING stays at 0.10: the 0-5%/5-10%/10-15% buckets
# don't show a single clean breakpoint (ROI wobbles -3.0%/-0.7%/-2.9%, likely
# reflecting the specific mix of markets/risk-levels landing in each bucket
# rather than a real threshold effect) — moving this value would not be
# backed by a real signal in the data the way the STRONG move is.
ALERT_THRESHOLD_INTERESTING = 0.10
ALERT_THRESHOLD_STRONG = 0.20


def expected_value(probability: float, bookmaker_odds: float) -> float:
    return probability * bookmaker_odds - 1.0


def discrepancy_pct(model_probability: float, bookmaker_odds: float) -> float:
    market_implied_probability = 1.0 / bookmaker_odds
    return (model_probability - market_implied_probability) / market_implied_probability


def classify_alert(discrepancy: float) -> AlertLevel:
    """STRONG does not mean "likely value" — the real backtest shows the
    opposite (see the threshold constants' docstring above): treat STRONG as
    "this pick disagrees a lot with the market, which has historically
    correlated with the model being wrong more often, not the market" — a
    caution flag, never a buy signal. The live `Alert.explanation` text this
    feeds (built in `analysis_runner.py`) and the frontend's alert copy both
    deliberately avoid the word "opportunity" or "mispricing" for this
    reason."""
    magnitude = abs(discrepancy)
    if magnitude > ALERT_THRESHOLD_STRONG:
        return AlertLevel.STRONG
    if magnitude >= ALERT_THRESHOLD_INTERESTING:
        return AlertLevel.INTERESTING
    return AlertLevel.NONE
