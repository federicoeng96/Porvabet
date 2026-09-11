import type { MatchDetailOut, MatchTableRowOut, RefreshResultOut } from "./types";

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

export function getMatchDetail(matchId: number): Promise<MatchDetailOut> {
  return getJson(`/matches/${matchId}`);
}

export function analyzeMatch(matchId: number): Promise<RefreshResultOut> {
  return getJson(`/matches/${matchId}/analyze`, { method: "POST" });
}
