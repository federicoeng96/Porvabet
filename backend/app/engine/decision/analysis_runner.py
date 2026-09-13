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

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.decision.count_market_estimates import (
    CountMarketEstimate,
    compute_count_market_estimates,
)
from app.engine.decision.reliability import model_reliability_for
from app.engine.decision.risk_score import RiskFactors
from app.engine.decision.selection import Candidate, build_risk_ladder
from app.engine.decision.value import classify_alert, discrepancy_pct, expected_value
from app.engine.statistical.dixon_coles import DixonColesModel, GoalMatchInput
from app.ingestion.match_ingestion import ingest_live_odds_quotes
from app.models.enums import AlertLevel, MarketCategory, MatchStatus, ModelFamily
from app.models.market import Market, MarketOutcome, OddsQuote
from app.models.match import Match
from app.models.prediction import Alert, AnalysisVersion, ModelVersion, Prediction, RiskSelection
from app.providers.base import build_default_odds_provider_chain
from app.providers.base.odds_provider import OddsProvider

logger = logging.getLogger(__name__)

MARKET_LABELS = {
    "MATCH_RESULT": "1X2",
    "TOTAL_GOALS": "Over/Under 2.5 goals",
    "CORNERS": "Over/Under corner totali",
    "CARDS": "Over/Under cartellini totali",
}
OUTCOME_LABELS = {
    ("MATCH_RESULT", "HOME"): "Home win",
    ("MATCH_RESULT", "DRAW"): "Draw",
    ("MATCH_RESULT", "AWAY"): "Away win",
    ("TOTAL_GOALS", "OVER"): "Over 2.5",
    ("TOTAL_GOALS", "UNDER"): "Under 2.5",
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


def run_analysis_for_match(
    db: Session,
    match_id: int,
    trigger: str = "manual_refresh",
    odds_provider: OddsProvider | None = None,
) -> AnalysisResult:
    match = db.get(Match, match_id)
    if match is None:
        raise ValueError(f"Match {match_id} not found")

    # Only for a not-yet-played fixture: a FINISHED match already has real
    # historical closing odds (see ingest_historical_match) and no live
    # market exists for it anymore, so skip this for every backtest/history
    # match — which is also what keeps this a no-op (no network call at all)
    # for the large majority of calls in this codebase's test suite.
    if match.status != MatchStatus.FINISHED:
        provider = odds_provider if odds_provider is not None else build_default_odds_provider_chain()
        _refresh_live_odds_for_match(db, match, provider)

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

    from app.models.core import Season

    competition_id = db.get(Season, match.season_id).competition_id
    candidates, prediction_rows = _build_candidates_and_predictions(
        db, match, model, model_version, analysis_version, uncertainty, competition_id
    )
    # `candidates` always has one entry per MATCH_RESULT/TOTAL_GOALS outcome once the
    # model has fit (5 outcomes, unconditionally — see _build_candidates_and_predictions):
    # a real Candidate with a real bookmaker_odds/value when a quote exists, otherwise
    # one with bookmaker_odds=None/value=None ("n/d"). The ladder is therefore always
    # buildable, even when literally no market anywhere has a quote (Betfair
    # unavailable and no historical closing odds — the normal case for a genuinely
    # future fixture) — Value/Alert are "n/d" on every level rather than the whole
    # analysis refusing to produce anything. See VERIFICATION_LOG.md for the real
    # fixture that first exposed the previous all-or-nothing behavior.
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


def _refresh_live_odds_for_match(db: Session, match: Match, odds_provider: OddsProvider) -> int:
    """Fetches current odds for `match` from `odds_provider` (e.g. the
    Betfair-Exchange-first chain from `build_default_odds_provider_chain`)
    and persists them as new OddsQuote rows via `ingest_live_odds_quotes`.

    Never raises and never fabricates: if the provider is unavailable (no
    credentials configured) or the fetch itself fails (network down,
    unexpected response), this logs and returns 0 — the rest of the analysis
    then proceeds exactly as before this feature existed, using whatever
    OddsQuote rows already exist (possibly none, in which case
    `_build_candidates_and_predictions` still produces a Candidate for that
    market, with bookmaker_odds=None/value="n/d" — never an invented price,
    and never a market silently missing from the ladder either).
    """
    if not odds_provider.is_available():
        return 0
    try:
        records = odds_provider.get_odds_for_match(
            match.home_team.name, match.away_team.name, match.kickoff_utc.isoformat()
        )
    except Exception:
        logger.exception(
            "Live odds refresh failed for match %s (%s vs %s) — continuing with "
            "whatever OddsQuote rows already exist.",
            match.id,
            match.home_team.name,
            match.away_team.name,
        )
        return 0
    return ingest_live_odds_quotes(db, match, records)


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


def _get_or_create_market(
    db: Session, match: Match, category: MarketCategory, label: str, line: float | None = None
) -> Market:
    market = db.scalar(
        select(Market).where(Market.match_id == match.id, Market.category == category)
    )
    if market is None:
        market = Market(match_id=match.id, category=category, label=label, line=line)
        db.add(market)
        db.flush()
    elif line is not None:
        market.line = line
    return market


def _get_or_create_outcome(db: Session, market: Market, code: str, label: str) -> MarketOutcome:
    outcome = db.scalar(
        select(MarketOutcome).where(MarketOutcome.market_id == market.id, MarketOutcome.code == code)
    )
    if outcome is None:
        outcome = MarketOutcome(market_id=market.id, code=code, label=label)
        db.add(outcome)
        db.flush()
    return outcome


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
    market = _get_or_create_market(
        db, match, category, MARKET_LABELS[estimate.market_category], line=estimate.line
    )
    outcomes = {
        code: _get_or_create_outcome(db, market, code, f"{code.title()} {estimate.line}")
        for code in ("OVER", "UNDER")
    }

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
    competition_id: int,
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

    candidates: list[Candidate] = []
    predictions: dict[str, Prediction] = {}

    # Get-or-create the Market/MarketOutcome scaffold for both markets rather
    # than only looking at whatever rows already happen to exist: a model
    # probability is always computable from the fitted Dixon-Coles model
    # regardless of whether any OddsQuote has ever been ingested for this
    # match, so every outcome below always gets a Prediction — never a
    # silently-missing row (see the odds_quote is None branch).
    market_by_category = {
        "MATCH_RESULT": _get_or_create_market(
            db, match, MarketCategory.MATCH_RESULT, MARKET_LABELS["MATCH_RESULT"]
        ),
        "TOTAL_GOALS": _get_or_create_market(
            db, match, MarketCategory.TOTAL_GOALS, MARKET_LABELS["TOTAL_GOALS"], line=2.5
        ),
    }

    for (category, code), probability in prob_by_category_code.items():
        market = market_by_category[category]
        outcome = _get_or_create_outcome(db, market, code, OUTCOME_LABELS[(category, code)])

        fair = 1.0 / probability
        odds_quote = db.scalar(
            select(OddsQuote)
            .where(OddsQuote.market_outcome_id == outcome.id)
            .order_by(OddsQuote.captured_at.desc())
        )
        bookmaker_odds = odds_quote.decimal_odds if odds_quote is not None else None

        # model_reliability never depends on whether a quote exists — it reads the
        # real backtest calibration curve for this market/competition regardless.
        reliability_estimate = model_reliability_for(
            db, ModelFamily.DIXON_COLES_POISSON, category, competition_id, probability
        )
        # Fail-conservative when the backtest evidence doesn't support a
        # confident estimate (see reliability.py docstring): 0.0 is the
        # worst-case reliability, maximizing this factor's risk
        # contribution rather than either (a) pretending 0.5-neutral like
        # the placeholder this replaces, or (b) hiding the candidate from
        # the ladder entirely — a market with a real quoted price and EV
        # stays visible to the user, just correctly flagged as higher risk.
        model_reliability = (
            reliability_estimate.value if reliability_estimate.value is not None else 0.0
        )

        factors = RiskFactors(
            probability=probability,
            bookmaker_odds=bookmaker_odds,
            uncertainty=uncertainty,
            data_quality=1.0,
            model_reliability=model_reliability,
            prediction_stability=1.0,
            lineup_dependency=0.0,
        )
        # A Candidate/Prediction is built unconditionally, whether or not a real
        # quote exists (see VERIFICATION_LOG.md — a real fixture with literally no
        # quote anywhere used to abort the whole analysis here). No liquid quote
        # from any configured source (BetfairExchangeOddsProvider/
        # FallbackOddsProvider) means bookmaker_odds/value stay explicitly None
        # ("n/d") — the model's own probability/fair-odds estimate is never
        # withheld, and the outcome still enters the risk ladder below, just
        # never with a guessed price. Same "n/d" principle already applied to
        # CORNERS/CARDS in count_market_estimates.py, now applied uniformly here
        # too instead of only when *some* (not all) markets lack a quote.
        candidate = Candidate(
            market_outcome_key=f"{category}:{code}",
            market_category=category,
            market_label=MARKET_LABELS.get(category, category),
            outcome_label=code,
            probability=probability,
            bookmaker_odds=bookmaker_odds,
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
            bookmaker_odds=bookmaker_odds,
            bookmaker_name=odds_quote.bookmaker if odds_quote is not None else None,
            value=(
                expected_value(probability, bookmaker_odds) if bookmaker_odds is not None else None
            ),
            uncertainty=uncertainty,
            confidence=1.0 - uncertainty,
        )
        db.add(prediction)
        db.flush()
        predictions[candidate.market_outcome_key] = prediction

        if odds_quote is not None:
            disc = discrepancy_pct(probability, odds_quote.decimal_odds)
            alert_level = classify_alert(disc)
            if alert_level != AlertLevel.NONE:
                db.add(
                    Alert(
                        prediction_id=prediction.id,
                        level=alert_level,
                        discrepancy_pct=disc,
                        explanation=(
                            f"{MARKET_LABELS.get(category, category)} {code}: "
                            f"probabilità modello {probability:.1%} vs probabilità "
                            f"implicita mercato {1 / odds_quote.decimal_odds:.1%}."
                        ),
                    )
                )

    return candidates, predictions


def _alt_rationale(item) -> str:
    c = item.candidate
    odds_part = f"quota {c.bookmaker_odds:.2f}" if c.bookmaker_odds is not None else "quota n/d"
    value_part = f"valore atteso {item.value:+.1%}" if item.value is not None else "valore atteso n/d"
    return f"Alternativa — {c.market_label} {c.outcome_label}: probabilità {c.probability:.1%}, {odds_part}, {value_part}."


def _mark_previous_versions_superseded(db: Session, match_id: int) -> None:
    db.query(AnalysisVersion).filter(
        AnalysisVersion.match_id == match_id, AnalysisVersion.is_current.is_(True)
    ).update({"is_current": False})
