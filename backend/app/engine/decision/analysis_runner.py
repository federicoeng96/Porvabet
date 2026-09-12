"""Orchestrates one full "AGGIORNA ANALISI" run for a single match.

This is the only place that ties together: historical data already in the DB ->
the statistical engine -> the decision layer (fair odds/value/risk/selection) ->
persisted AnalysisVersion/Prediction/RiskSelection/Alert rows. It intentionally
knows nothing about HTTP — the FastAPI layer just calls `run_analysis_for_match`
and serializes the result.

No-leakage boundary: the Dixon-Coles model is fit only on FINISHED matches in the
same competition whose kickoff is strictly before the target match's kickoff.
Odds are read from whatever OddsQuote rows are already attached to the target
match's markets (ingested by `app.ingestion.match_ingestion`) — this module does
not call any OddsProvider itself, so it works the same whether those quotes came
from historical closing odds (the only real odds source in this slice — see
DATA_SOURCES.md on ePlay24) or a future live feed.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.decision.count_market_estimates import (
    CountMarketEstimate,
    compute_count_market_estimates,
)
from app.engine.decision.risk_score import RiskFactors
from app.engine.decision.selection import Candidate, build_risk_ladder
from app.engine.decision.value import classify_alert, discrepancy_pct, expected_value
from app.engine.statistical.dixon_coles import DixonColesModel, GoalMatchInput
from app.models.enums import AlertLevel, MarketCategory, MatchStatus, ModelFamily
from app.models.market import Market, MarketOutcome, OddsQuote
from app.models.match import Match
from app.models.prediction import Alert, AnalysisVersion, ModelVersion, Prediction, RiskSelection

MARKET_LABELS = {
    "MATCH_RESULT": "1X2",
    "TOTAL_GOALS": "Over/Under 2.5 goals",
    "CORNERS": "Over/Under corner totali",
    "CARDS": "Over/Under cartellini totali",
}
MIN_TRAINING_MATCHES = 40


class InsufficientDataError(RuntimeError):
    """Raised when there isn't enough prior data to produce a responsible analysis —
    per the brief, better to produce nothing than to fabricate a selection."""


@dataclass(frozen=True)
class AnalysisResult:
    analysis_version_id: int
    risk_levels: list[dict]
    count_market_estimates_computed: int  # CORNERS/CARDS: probability-only, no odds — see count_market_estimates.py


def run_analysis_for_match(db: Session, match_id: int, trigger: str = "manual_refresh") -> AnalysisResult:
    match = db.get(Match, match_id)
    if match is None:
        raise ValueError(f"Match {match_id} not found")

    training_matches = _load_training_matches(db, match)
    if len(training_matches) < MIN_TRAINING_MATCHES:
        raise InsufficientDataError(
            f"Only {len(training_matches)} prior finished matches available for this "
            f"competition (need >= {MIN_TRAINING_MATCHES}); refusing to fabricate a "
            f"prediction from insufficient history."
        )

    model = DixonColesModel()
    model.fit(training_matches, as_of=match.kickoff_utc.date())

    model_version = _get_or_create_model_version(db, match, model)

    home_name, away_name = match.home_team.name, match.away_team.name
    if home_name not in model.params.teams or away_name not in model.params.teams:
        raise InsufficientDataError(
            f"'{home_name}' or '{away_name}' has no prior match history in this "
            f"competition before {match.kickoff_utc.date()} — cannot fit team strength."
        )

    train_n = len(training_matches)
    uncertainty = max(0.0, 1.0 - min(train_n, 300) / 300)

    _mark_previous_versions_superseded(db, match_id)
    analysis_version = AnalysisVersion(
        match_id=match_id,
        computed_at=datetime.now(UTC),
        is_current=True,
        trigger=trigger,
    )
    db.add(analysis_version)
    db.flush()

    candidates, prediction_rows = _build_candidates_and_predictions(
        db, match, model, model_version, analysis_version, uncertainty
    )
    if not candidates:
        raise InsufficientDataError(
            "No market has both a model probability and a bookmaker odds quote for "
            "this match — nothing to analyze."
        )

    ladder = build_risk_ladder(candidates)

    risk_levels_out = []
    for level_selection in ladder:
        main_pred = prediction_rows[level_selection.main.candidate.market_outcome_key]
        main_row = RiskSelection(
            analysis_version_id=analysis_version.id,
            risk_level=level_selection.risk_level,
            rank=1,
            prediction_id=main_pred.id,
            risk_score_raw=level_selection.main.risk_raw,
            rationale=level_selection.rationale,
        )
        db.add(main_row)

        alt_rows = []
        for rank, alt in enumerate(level_selection.alternatives, start=2):
            alt_pred = prediction_rows[alt.candidate.market_outcome_key]
            alt_row = RiskSelection(
                analysis_version_id=analysis_version.id,
                risk_level=level_selection.risk_level,
                rank=rank,
                prediction_id=alt_pred.id,
                risk_score_raw=alt.risk_raw,
                rationale=_alt_rationale(alt),
            )
            db.add(alt_row)
            alt_rows.append(alt_row)

        risk_levels_out.append(
            {
                "risk_level": level_selection.risk_level,
                "main": level_selection.main,
                "alternatives": level_selection.alternatives,
            }
        )

    count_estimates = compute_count_market_estimates(db, match)
    for estimate in count_estimates:
        count_model_version = _get_or_create_count_model_version(db, match, estimate)
        _persist_count_market_estimate(db, match, count_model_version, analysis_version, estimate)

    db.flush()
    return AnalysisResult(
        analysis_version_id=analysis_version.id,
        risk_levels=risk_levels_out,
        count_market_estimates_computed=len(count_estimates),
    )


def _get_or_create_count_model_version(
    db: Session, match: Match, estimate: CountMarketEstimate
) -> ModelVersion:
    """Separate ModelVersion per count market (CORNERS/CARDS have independently
    fitted attack/defense ratings) — never reuses the Dixon-Coles ModelVersion,
    which would misrepresent which model actually produced the prediction."""
    from app.models.core import Season

    season = db.get(Season, match.season_id)
    version_label = (
        f"poisson_count-{estimate.market_category}-{match.kickoff_utc.date().isoformat()}"
    )
    existing = db.scalar(
        select(ModelVersion).where(
            ModelVersion.competition_id == season.competition_id,
            ModelVersion.version_label == version_label,
        )
    )
    if existing:
        return existing
    mv = ModelVersion(
        family=ModelFamily.POISSON_COUNT_MODEL,
        market_category=estimate.market_category,
        competition_id=season.competition_id,
        version_label=version_label,
        trained_at=datetime.now(UTC),
        training_data_cutoff=datetime.combine(
            match.kickoff_utc.date(), datetime.min.time(), tzinfo=UTC
        ),
        notes=f"n_training_matches={estimate.n_training_matches}, line={estimate.line}",
    )
    db.add(mv)
    db.flush()
    return mv


def _persist_count_market_estimate(
    db: Session,
    match: Match,
    model_version: ModelVersion,
    analysis_version: AnalysisVersion,
    estimate: CountMarketEstimate,
) -> None:
    """Persists a CORNERS/CARDS probability estimate as a Prediction with
    `bookmaker_odds=None` / `value=None` — deliberately never given a
    `Candidate`/RiskSelection, since those require a real price (see
    count_market_estimates.py docstring)."""
    category = MarketCategory[estimate.market_category]
    market = db.scalar(
        select(Market).where(Market.match_id == match.id, Market.category == category)
    )
    if market is None:
        market = Market(
            match_id=match.id,
            category=category,
            label=MARKET_LABELS[estimate.market_category],
            line=estimate.line,
        )
        db.add(market)
        db.flush()

    outcomes = {}
    for code, label in (("OVER", f"Over {estimate.line}"), ("UNDER", f"Under {estimate.line}")):
        outcome = db.scalar(
            select(MarketOutcome).where(MarketOutcome.market_id == market.id, MarketOutcome.code == code)
        )
        if outcome is None:
            outcome = MarketOutcome(market_id=market.id, code=code, label=label)
            db.add(outcome)
            db.flush()
        outcomes[code] = outcome

    uncertainty = max(0.0, 1.0 - min(estimate.n_training_matches, 300) / 300)
    for code, probability in (("OVER", estimate.probability_over), ("UNDER", estimate.probability_under)):
        db.add(
            Prediction(
                analysis_version_id=analysis_version.id,
                market_outcome_id=outcomes[code].id,
                model_version_id=model_version.id,
                probability=probability,
                fair_odds=1.0 / probability,
                bookmaker_odds=None,
                bookmaker_name=None,
                value=None,
                uncertainty=uncertainty,
                confidence=1.0 - uncertainty,
            )
        )


def _load_training_matches(db: Session, match: Match) -> list[GoalMatchInput]:
    from app.models.core import Season

    season = db.get(Season, match.season_id)
    prior = db.scalars(
        select(Match)
        .join(Season, Match.season_id == Season.id)
        .where(
            Season.competition_id == season.competition_id,
            Match.status == MatchStatus.FINISHED,
            Match.kickoff_utc < match.kickoff_utc,
            Match.home_goals_ft.is_not(None),
        )
    ).all()
    return [
        GoalMatchInput(
            home_team=m.home_team.name,
            away_team=m.away_team.name,
            home_goals=m.home_goals_ft,
            away_goals=m.away_goals_ft,
            match_date=m.kickoff_utc.date(),
        )
        for m in prior
    ]


def _get_or_create_model_version(db: Session, match: Match, model: DixonColesModel) -> ModelVersion:
    from app.models.core import Season

    season = db.get(Season, match.season_id)
    version_label = f"dixon_coles-{model.params.training_cutoff.isoformat()}"
    existing = db.scalar(
        select(ModelVersion).where(
            ModelVersion.competition_id == season.competition_id,
            ModelVersion.version_label == version_label,
        )
    )
    if existing:
        return existing
    mv = ModelVersion(
        family=ModelFamily.DIXON_COLES_POISSON,
        market_category="MATCH_RESULT,TOTAL_GOALS",
        competition_id=season.competition_id,
        version_label=version_label,
        trained_at=model.params.fitted_at,
        training_data_cutoff=datetime.combine(
            model.params.training_cutoff, datetime.min.time(), tzinfo=UTC
        ),
        notes=f"xi={model.xi}, n_matches={model.params.n_matches}, home_adv={model.params.home_advantage:.3f}, rho={model.params.rho:.3f}",
    )
    db.add(mv)
    db.flush()
    return mv


def _build_candidates_and_predictions(
    db: Session,
    match: Match,
    model: DixonColesModel,
    model_version: ModelVersion,
    analysis_version: AnalysisVersion,
    uncertainty: float,
) -> tuple[list[Candidate], dict[str, Prediction]]:
    home_name, away_name = match.home_team.name, match.away_team.name
    result_probs = model.match_result_probabilities(home_name, away_name)
    total_goals_probs = model.total_goals_probabilities(home_name, away_name, line=2.5)
    prob_by_category_code = {
        ("MATCH_RESULT", "HOME"): result_probs["HOME"],
        ("MATCH_RESULT", "DRAW"): result_probs["DRAW"],
        ("MATCH_RESULT", "AWAY"): result_probs["AWAY"],
        ("TOTAL_GOALS", "OVER"): total_goals_probs["OVER"],
        ("TOTAL_GOALS", "UNDER"): total_goals_probs["UNDER"],
    }

    markets = db.scalars(select(Market).where(Market.match_id == match.id)).all()

    candidates: list[Candidate] = []
    predictions: dict[str, Prediction] = {}

    for market in markets:
        category = market.category.value if hasattr(market.category, "value") else market.category
        if category not in ("MATCH_RESULT", "TOTAL_GOALS"):
            continue
        outcomes = db.scalars(select(MarketOutcome).where(MarketOutcome.market_id == market.id)).all()
        for outcome in outcomes:
            key = (category, outcome.code)
            if key not in prob_by_category_code:
                continue
            odds_quote = db.scalar(
                select(OddsQuote)
                .where(OddsQuote.market_outcome_id == outcome.id)
                .order_by(OddsQuote.captured_at.desc())
            )
            if odds_quote is None:
                continue

            probability = prob_by_category_code[key]
            fair = 1.0 / probability
            value = expected_value(probability, odds_quote.decimal_odds)
            disc = discrepancy_pct(probability, odds_quote.decimal_odds)
            alert_level = classify_alert(disc)

            factors = RiskFactors(
                probability=probability,
                bookmaker_odds=odds_quote.decimal_odds,
                uncertainty=uncertainty,
                data_quality=1.0,
                model_reliability=0.5,
                prediction_stability=1.0,
                lineup_dependency=0.0,
            )
            candidate = Candidate(
                market_outcome_key=f"{category}:{outcome.code}",
                market_category=category,
                market_label=MARKET_LABELS.get(category, category),
                outcome_label=outcome.code,
                probability=probability,
                bookmaker_odds=odds_quote.decimal_odds,
                fair_odds_value=fair,
                risk_factors=factors,
            )
            candidates.append(candidate)

            prediction = Prediction(
                analysis_version_id=analysis_version.id,
                market_outcome_id=outcome.id,
                model_version_id=model_version.id,
                probability=probability,
                fair_odds=fair,
                bookmaker_odds=odds_quote.decimal_odds,
                bookmaker_name=odds_quote.bookmaker,
                value=value,
                uncertainty=uncertainty,
                confidence=1.0 - uncertainty,
            )
            db.add(prediction)
            db.flush()
            predictions[candidate.market_outcome_key] = prediction

            if alert_level != AlertLevel.NONE:
                db.add(
                    Alert(
                        prediction_id=prediction.id,
                        level=alert_level,
                        discrepancy_pct=disc,
                        explanation=(
                            f"{MARKET_LABELS.get(category, category)} {outcome.code}: "
                            f"probabilità modello {probability:.1%} vs probabilità "
                            f"implicita mercato {1 / odds_quote.decimal_odds:.1%}."
                        ),
                    )
                )

    return candidates, predictions


def _alt_rationale(item) -> str:
    c = item.candidate
    return (
        f"Alternativa — {c.market_label} {c.outcome_label}: probabilità {c.probability:.1%}, "
        f"quota {c.bookmaker_odds:.2f}, valore atteso {item.value:+.1%}."
    )


def _mark_previous_versions_superseded(db: Session, match_id: int) -> None:
    db.query(AnalysisVersion).filter(
        AnalysisVersion.match_id == match_id, AnalysisVersion.is_current.is_(True)
    ).update({"is_current": False})
