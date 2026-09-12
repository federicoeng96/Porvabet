export interface AlertOut {
  level: "NONE" | "INTERESTING" | "STRONG";
  discrepancy_pct: number;
  explanation: string;
}

export interface SelectionOut {
  market_category: string;
  market_label: string;
  outcome_label: string;
  probability: number;
  bookmaker_odds: number;
  bookmaker_name: string | null;
  fair_odds: number;
  value: number;
  uncertainty: number;
  confidence: number;
  rationale: string;
  alert: AlertOut | null;
}

export interface RiskLevelOut {
  risk_level: number;
  main: SelectionOut;
  alternatives: SelectionOut[];
}

export interface CountEstimateOut {
  market_category: string;
  market_label: string;
  line: number;
  probability_over: number;
  probability_under: number;
  fair_odds_over: number;
  fair_odds_under: number;
  note: string;
}

export interface MatchSummaryOut {
  id: number;
  competition_code: string;
  kickoff_utc: string;
  home_team: string;
  away_team: string;
  status: string;
  has_current_analysis: boolean;
}

export interface MatchDetailOut extends MatchSummaryOut {
  analysis_version_id: number | null;
  computed_at: string | null;
  risk_levels: RiskLevelOut[];
  additional_estimates: CountEstimateOut[];
}

export interface MatchTableRowOut {
  id: number;
  kickoff_utc: string;
  home_team: string;
  away_team: string;
  risk_level: number;
  selection: SelectionOut;
  info: string;
}

export interface RefreshResultOut {
  match_id: number;
  analysis_version_id: number;
  risk_levels_computed: number;
}

export interface BatchRefreshItemOut {
  match_id: number;
  status: "ok" | "insufficient_data" | "error";
  analysis_version_id: number | null;
  risk_levels_computed: number | null;
  error: string | null;
}

export interface BatchRefreshResultOut {
  total: number;
  succeeded: number;
  insufficient_data: number;
  failed: number;
  results: BatchRefreshItemOut[];
}
