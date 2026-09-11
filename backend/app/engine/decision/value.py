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

# Provisional thresholds from the brief, explicitly flagged as needing
# recalibration once BACKTEST_SPEC.md's calibration analysis has enough
# volume to judge whether they actually separate profitable from unprofitable
# discrepancies for this model.
ALERT_THRESHOLD_INTERESTING = 0.10
ALERT_THRESHOLD_STRONG = 0.15


def expected_value(probability: float, bookmaker_odds: float) -> float:
    return probability * bookmaker_odds - 1.0


def discrepancy_pct(model_probability: float, bookmaker_odds: float) -> float:
    market_implied_probability = 1.0 / bookmaker_odds
    return (model_probability - market_implied_probability) / market_implied_probability


def classify_alert(discrepancy: float) -> AlertLevel:
    magnitude = abs(discrepancy)
    if magnitude > ALERT_THRESHOLD_STRONG:
        return AlertLevel.STRONG
    if magnitude >= ALERT_THRESHOLD_INTERESTING:
        return AlertLevel.INTERESTING
    return AlertLevel.NONE


def alert_explanation(
    market_label: str,
    outcome_label: str,
    model_probability: float,
    bookmaker_odds: float,
    fair_odds_value: float,
    value: float,
    level: AlertLevel,
) -> str:
    """Human-readable explanation for the alert popover. Language deliberately
    avoids asserting the market is wrong (see brief: never "quota sicuramente
    sbagliata")."""
    if level == AlertLevel.NONE:
        qualifier = "nessuna discrepanza rilevante"
    elif level == AlertLevel.INTERESTING:
        qualifier = "discrepanza modello-mercato interessante"
    else:
        qualifier = "discrepanza modello-mercato marcata (potenziale mispricing)"
    return (
        f"{market_label} — {outcome_label}: probabilità modello {model_probability:.1%}, "
        f"quota bookmaker {bookmaker_odds:.2f} (quota fair stimata {fair_odds_value:.2f}), "
        f"edge stimato {value:+.1%}. {qualifier}: la stima del modello differisce dalla "
        f"probabilità implicita dal mercato; non è una garanzia che la quota sia sbagliata."
    )
