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
