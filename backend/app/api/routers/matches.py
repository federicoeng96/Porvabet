from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.engine.decision.analysis_runner import InsufficientDataError, run_analysis_for_match
from app.engine.decision.count_market_estimates import NO_ODDS_NOTE
from app.models.market import Market, MarketOutcome
from app.models.match import Match
from app.models.prediction import Alert, AnalysisVersion, Prediction, RiskSelection
from app.schemas.analysis import (
    AlertOut,
    BatchAnalyzeRequest,
    BatchRefreshItemOut,
    BatchRefreshResultOut,
    CountEstimateOut,
    MatchDetailOut,
    MatchSummaryOut,
    MatchTableRowOut,
    RefreshResultOut,
    RiskLevelOut,
    SelectionOut,
)

router = APIRouter(prefix="/matches", tags=["matches"])


def _selection_out(db: Session, prediction: Prediction, rationale: str) -> SelectionOut:
    outcome = db.get(MarketOutcome, prediction.market_outcome_id)
    market = db.get(Market, outcome.market_id)
    alert = db.scalar(select(Alert).where(Alert.prediction_id == prediction.id))
    category = market.category.value if hasattr(market.category, "value") else market.category
    return SelectionOut(
        market_category=category,
        market_label=market.label,
        outcome_label=outcome.code,
        probability=prediction.probability,
        bookmaker_odds=prediction.bookmaker_odds,
        bookmaker_name=prediction.bookmaker_name,
        fair_odds=prediction.fair_odds,
        value=prediction.value or 0.0,
        uncertainty=prediction.uncertainty,
        confidence=prediction.confidence,
        rationale=rationale,
        alert=(
            AlertOut(
                level=alert.level.value if hasattr(alert.level, "value") else alert.level,
                discrepancy_pct=alert.discrepancy_pct,
                explanation=alert.explanation,
            )
            if alert
            else None
        ),
    )


def _count_estimates_out(db: Session, analysis_version_id: int) -> list[CountEstimateOut]:
    """CORNERS/CARDS Prediction rows have bookmaker_odds=None by construction
    (see count_market_estimates.py) — that's exactly how we identify them here,
    rather than a separate flag."""
    predictions = db.scalars(
        select(Prediction).where(
            Prediction.analysis_version_id == analysis_version_id,
            Prediction.bookmaker_odds.is_(None),
        )
    ).all()

    by_market: dict[int, list[Prediction]] = {}
    for pred in predictions:
        outcome = db.get(MarketOutcome, pred.market_outcome_id)
        by_market.setdefault(outcome.market_id, []).append(pred)

    out = []
    for market_id, preds in by_market.items():
        market = db.get(Market, market_id)
        over_pred = next(
            p for p in preds if db.get(MarketOutcome, p.market_outcome_id).code == "OVER"
        )
        under_pred = next(
            p for p in preds if db.get(MarketOutcome, p.market_outcome_id).code == "UNDER"
        )
        category = market.category.value if hasattr(market.category, "value") else market.category
        out.append(
            CountEstimateOut(
                market_category=category,
                market_label=market.label,
                line=market.line,
                probability_over=over_pred.probability,
                probability_under=under_pred.probability,
                fair_odds_over=over_pred.fair_odds,
                fair_odds_under=under_pred.fair_odds,
                note=NO_ODDS_NOTE,
            )
        )
    return out


def _match_summary(db: Session, match: Match, has_analysis: bool) -> MatchSummaryOut:
    from app.models.core import Competition, Season

    season = db.get(Season, match.season_id)
    competition = db.get(Competition, season.competition_id)
    return MatchSummaryOut(
        id=match.id,
        competition_code=competition.code,
        kickoff_utc=match.kickoff_utc,
        home_team=match.home_team.name,
        away_team=match.away_team.name,
        status=match.status.value if hasattr(match.status, "value") else match.status,
        has_current_analysis=has_analysis,
    )


@router.get("", response_model=list[MatchTableRowOut])
def list_matches_at_risk_level(risk_level: int = 5, db: Session = Depends(get_db)):
    if not 1 <= risk_level <= 10:
        raise HTTPException(400, "risk_level must be between 1 and 10")

    rows = []
    matches = db.scalars(select(Match).order_by(Match.kickoff_utc)).all()
    for match in matches:
        analysis_version = db.scalar(
            select(AnalysisVersion).where(
                AnalysisVersion.match_id == match.id, AnalysisVersion.is_current.is_(True)
            )
        )
        if analysis_version is None:
            continue
        main_selection = db.scalar(
            select(RiskSelection).where(
                RiskSelection.analysis_version_id == analysis_version.id,
                RiskSelection.risk_level == risk_level,
                RiskSelection.rank == 1,
            )
        )
        if main_selection is None:
            continue
        prediction = db.get(Prediction, main_selection.prediction_id)
        selection = _selection_out(db, prediction, main_selection.rationale)
        info = f"Risk {risk_level} · {selection.market_label} {selection.outcome_label}"
        rows.append(
            MatchTableRowOut(
                id=match.id,
                kickoff_utc=match.kickoff_utc,
                home_team=match.home_team.name,
                away_team=match.away_team.name,
                risk_level=risk_level,
                selection=selection,
                info=info,
            )
        )
    return rows


@router.get("/{match_id}", response_model=MatchDetailOut)
def get_match_detail(match_id: int, db: Session = Depends(get_db)):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(404, "Match not found")

    analysis_version = db.scalar(
        select(AnalysisVersion).where(
            AnalysisVersion.match_id == match_id, AnalysisVersion.is_current.is_(True)
        )
    )
    summary = _match_summary(db, match, analysis_version is not None)

    if analysis_version is None:
        return MatchDetailOut(
            **summary.model_dump(), analysis_version_id=None, computed_at=None, risk_levels=[]
        )

    risk_levels_out = []
    for level in range(1, 11):
        selections = db.scalars(
            select(RiskSelection)
            .where(
                RiskSelection.analysis_version_id == analysis_version.id,
                RiskSelection.risk_level == level,
            )
            .order_by(RiskSelection.rank)
        ).all()
        if not selections:
            continue
        main = next(s for s in selections if s.rank == 1)
        alts = [s for s in selections if s.rank != 1]
        risk_levels_out.append(
            RiskLevelOut(
                risk_level=level,
                main=_selection_out(db, db.get(Prediction, main.prediction_id), main.rationale),
                alternatives=[
                    _selection_out(db, db.get(Prediction, a.prediction_id), a.rationale) for a in alts
                ],
            )
        )

    return MatchDetailOut(
        **summary.model_dump(),
        analysis_version_id=analysis_version.id,
        computed_at=analysis_version.computed_at,
        risk_levels=risk_levels_out,
        additional_estimates=_count_estimates_out(db, analysis_version.id),
    )


@router.post("/{match_id}/analyze", response_model=RefreshResultOut)
def analyze_match(match_id: int, db: Session = Depends(get_db)):
    try:
        result = run_analysis_for_match(db, match_id)
    except InsufficientDataError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    db.commit()
    return RefreshResultOut(
        match_id=match_id,
        analysis_version_id=result.analysis_version_id,
        risk_levels_computed=len(result.risk_levels),
    )


@router.post("/analyze-batch", response_model=BatchRefreshResultOut)
def analyze_matches_batch(payload: BatchAnalyzeRequest, db: Session = Depends(get_db)):
    """Runs `run_analysis_for_match` for every match in `payload.match_ids`
    (or every match in the DB if omitted) in one request, instead of the
    frontend firing N parallel `/analyze` calls (ROADMAP.md item 10). Each
    match is committed independently: one match's `InsufficientDataError` (an
    expected, per-match condition — e.g. not enough prior history yet) or
    unexpected failure must not roll back or block every other match in the
    same batch, so failures are collected per item rather than raised.
    """
    if payload.match_ids is not None:
        match_ids = payload.match_ids
    else:
        match_ids = list(db.scalars(select(Match.id)).all())

    results: list[BatchRefreshItemOut] = []
    succeeded = insufficient_data = failed = 0

    for match_id in match_ids:
        try:
            result = run_analysis_for_match(db, match_id)
            db.commit()
            succeeded += 1
            results.append(
                BatchRefreshItemOut(
                    match_id=match_id,
                    status="ok",
                    analysis_version_id=result.analysis_version_id,
                    risk_levels_computed=len(result.risk_levels),
                )
            )
        except InsufficientDataError as exc:
            db.rollback()
            insufficient_data += 1
            results.append(BatchRefreshItemOut(match_id=match_id, status="insufficient_data", error=str(exc)))
        except Exception as exc:  # noqa: BLE001 -- one match's failure must not abort the whole batch
            db.rollback()
            failed += 1
            results.append(BatchRefreshItemOut(match_id=match_id, status="error", error=str(exc)))

    return BatchRefreshResultOut(
        total=len(match_ids),
        succeeded=succeeded,
        insufficient_data=insufficient_data,
        failed=failed,
        results=results,
    )
