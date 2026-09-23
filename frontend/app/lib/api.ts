import type {
  BatchRefreshResultOut,
  MatchDetailOut,
  MatchSummaryOut,
  MatchTableRowOut,
  RefreshResultOut,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${path} failed: ${res.status} ${body}`);
  }
  return res.json() as Promise<T>;
}

export function listMatchesAtRiskLevel(riskLevel: number): Promise<MatchTableRowOut[]> {
  return getJson(`/matches?risk_level=${riskLevel}`);
}

// Every current fixture (SCHEDULED/IN_PLAY), analyzed or not — unlike
// listMatchesAtRiskLevel above, which only returns matches that ALREADY
// have a current analysis (empty before the very first "AGGIORNA ANALISI"
// ever runs). This is the list to build analyze-batch's match_ids from.
export function listFixtures(): Promise<MatchSummaryOut[]> {
  return getJson(`/matches/fixtures`);
}

export function getMatchDetail(matchId: number): Promise<MatchDetailOut> {
  return getJson(`/matches/${matchId}`);
}

export function analyzeMatch(matchId: number): Promise<RefreshResultOut> {
  return getJson(`/matches/${matchId}/analyze`, { method: "POST" });
}

export function analyzeMatchesBatch(matchIds: number[]): Promise<BatchRefreshResultOut> {
  return getJson(`/matches/analyze-batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ match_ids: matchIds }),
  });
}
