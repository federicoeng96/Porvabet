"""Fair-odds conversion.

`fair_odds = 1 / probability` is the base formula requested by the brief. It is
deliberately the *only* thing this function does: it assumes `probability` is
already the model's best calibrated estimate. Refinements — a margin-free
"true probability" adjustment, blending with market-implied probability, or a
calibration-curve correction — belong in the calibration step of the modeling
pipeline (see MODEL_SPEC.md "Calibration"), not here, so that this conversion
stays a pure, auditable formula.
"""


def fair_odds(probability: float) -> float:
    if not (0.0 < probability <= 1.0):
        raise ValueError(f"probability must be in (0, 1], got {probability}")
    return 1.0 / probability
