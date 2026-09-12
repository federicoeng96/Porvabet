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


class NoOddsEstimateOut(BaseModel):
    """A model probability/fair-odds estimate for a market outcome that
    currently has no real bookmaker/exchange quote to compute value/risk
    against — Value/Alert are explicitly "n/d" (never fabricated), and the
    outcome never enters the risk ladder (`RiskLevelOut`), since that
    requires a real price. One row per outcome — not a fixed OVER/UNDER
    pair — so this covers both CORNERS/CARDS (no odds source at all for
    these markets yet) and MATCH_RESULT/TOTAL_GOALS on a fixture where the
    live odds provider (e.g. Betfair) has no liquid quote yet (common days
    before kickoff), never a row silently missing. See DATA_SOURCES.md."""

    market_category: str
    market_label: str
    outcome_label: str
    line: float | None
    probability: float
    fair_odds: float
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
    additional_estimates: list[NoOddsEstimateOut] = []


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


class BatchAnalyzeRequest(BaseModel):
    # None = every match in the DB; otherwise exactly the given ids (e.g. the
    # set currently displayed in the frontend table) — see matches.py.
    match_ids: list[int] | None = None


class BatchRefreshItemOut(BaseModel):
    match_id: int
    status: str  # "ok" | "insufficient_data" | "error"
    analysis_version_id: int | None = None
    risk_levels_computed: int | None = None
    error: str | None = None


class BatchRefreshResultOut(BaseModel):
    total: int
    succeeded: int
    insufficient_data: int
    failed: int
    results: list[BatchRefreshItemOut]
