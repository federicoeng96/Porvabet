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
  // null ("n/d") when no market anywhere has a real quote for this outcome —
  // the risk ladder still shows the row (probability/fair_odds always
  // present), it just never fabricates a price. See VERIFICATION_LOG.md.
  bookmaker_odds: number | null;
  bookmaker_name: string | null;
  fair_odds: number;
  value: number | null;
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

export interface NoOddsEstimateOut {
  market_category: string;
  market_label: string;
  outcome_label: string;
  line: number | null;
  probability: number;
  fair_odds: number;
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
  additional_estimates: NoOddsEstimateOut[];
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
