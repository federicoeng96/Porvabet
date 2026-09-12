from datetime import datetime

from pydantic import BaseModel


class AlertOut(BaseModel):
    level: str
    discrepancy_pct: float
    explanation: str


class SelectionOut(BaseModel):
    market_category: str
    market_label: str
    outcome_label: str
    probability: float
    bookmaker_odds: float
    bookmaker_name: str | None
    fair_odds: float
    value: float
    uncertainty: float
    confidence: float
    rationale: str
    alert: AlertOut | None = None


class RiskLevelOut(BaseModel):
    risk_level: int
    main: SelectionOut
    alternatives: list[SelectionOut]


class CountEstimateOut(BaseModel):
    """CORNERS/CARDS: probability-only estimate, no market odds available for
    these markets in the currently integrated data sources — see
    DATA_SOURCES.md. Never part of the risk ladder (no value/risk computable
    without a real price)."""

    market_category: str
    market_label: str
    line: float
    probability_over: float
    probability_under: float
    fair_odds_over: float
    fair_odds_under: float
    note: str


class MatchSummaryOut(BaseModel):
    id: int
    competition_code: str
    kickoff_utc: datetime
    home_team: str
    away_team: str
    status: str
    has_current_analysis: bool


class MatchDetailOut(MatchSummaryOut):
    analysis_version_id: int | None
    computed_at: datetime | None
    risk_levels: list[RiskLevelOut]
    additional_estimates: list[CountEstimateOut] = []


class MatchTableRowOut(BaseModel):
    id: int
    kickoff_utc: datetime
    home_team: str
    away_team: str
    risk_level: int
    selection: SelectionOut
    info: str


class RefreshResultOut(BaseModel):
    match_id: int
    analysis_version_id: int
    risk_levels_computed: int
