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
    # None ("n/d") when no market anywhere has a real quote for this outcome —
    # the risk ladder is still built (probability/fair_odds always present), just
    # never with a fabricated price. See VERIFICATION_LOG.md.
    bookmaker_odds: float | None
    bookmaker_name: str | None
    fair_odds: float
    value: float | None
    uncertainty: float
    confidence: float
    rationale: str
    alert: AlertOut | None = None


class RiskLevelOut(BaseModel):
    risk_level: int
    main: SelectionOut
    alternatives: list[SelectionOut]


class NoOddsEstimateOut(BaseModel):
    """A model probability/fair-odds estimate for a market outcome that has no
    real bookmaker/exchange quote AND is never part of the risk ladder
    mechanism at all — today that means CORNERS/CARDS only (no odds source
    integrated for these markets in this project, see DATA_SOURCES.md).
    MATCH_RESULT/TOTAL_GOALS outcomes without a quote instead show up inside
    `RiskLevelOut` itself (`SelectionOut.bookmaker_odds`/`value` = None, i.e.
    "n/d") since those two markets always enter the ladder now, priced or not
    — see VERIFICATION_LOG.md. One row per outcome — not a fixed OVER/UNDER
    pair."""

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
