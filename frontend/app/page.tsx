"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AlertPopover from "./components/AlertPopover";
import BetSlip, { type BetSlipItem } from "./components/BetSlip";
import RiskPill from "./components/RiskPill";
import { analyzeMatchesBatch, getMatchDetail, listFixtures, listMatchesAtRiskLevel } from "./lib/api";
import type { MatchDetailOut } from "./lib/types";

export default function HomePage() {
  const [matches, setMatches] = useState<MatchDetailOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [groupRisk, setGroupRisk] = useState(5);
  const [perMatchRisk, setPerMatchRisk] = useState<Record<number, number>>({});
  const [refreshing, setRefreshing] = useState(false);
  const [openAlertFor, setOpenAlertFor] = useState<number | null>(null);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const summaries = await listMatchesAtRiskLevel(1);
      const details = await Promise.all(summaries.map((s) => getMatchDetail(s.id)));
      details.sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc));
      setMatches(details);
    } catch (e) {
      setError(
        `Impossibile contattare il backend (${(e as Error).message}). Verifica che l'API sia ` +
          "avviata e che sia stato eseguito scripts/seed_dev_fixture.py o un'ingestione reale."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  function effectiveRisk(matchId: number): number {
    return perMatchRisk[matchId] ?? groupRisk;
  }

  function handleGroupRiskChange(value: number) {
    setGroupRisk(value);
    setPerMatchRisk({});
  }

  function handleMatchRiskChange(matchId: number, value: number) {
    setPerMatchRisk((prev) => ({ ...prev, [matchId]: value }));
  }

  async function handleRefreshAll() {
    setRefreshing(true);
    try {
      // `matches` state comes from listMatchesAtRiskLevel (GET /matches?risk_level=N),
      // which only returns matches that ALREADY have a current analysis — empty
      // before the very first analysis ever runs, which made this button send
      // analyze-batch an empty match_ids list and do nothing (see CHANGELOG.md).
      // listFixtures() fetches the real, current fixture universe instead, so
      // this works whether or not anything has been analyzed yet.
      const fixtures = await listFixtures();
      // One batch request instead of N parallel /analyze calls (ROADMAP.md item 10).
      await analyzeMatchesBatch(fixtures.map((f) => f.id));
      await loadAll();
    } finally {
      setRefreshing(false);
    }
  }

  const betSlipItems: BetSlipItem[] = useMemo(
    () =>
      matches
        .map((m) => {
          const level = effectiveRisk(m.id);
          const riskLevelData = m.risk_levels.find((rl) => rl.risk_level === level);
          // A main selection with no real quote ("n/d") has no real price to
          // stake against — excluded from the automatic bet slip (whose total
          // quote is a real product of real odds), even though it's still
          // shown, navigable, in the main table above.
          if (!riskLevelData || riskLevelData.main.bookmaker_odds === null) return null;
          return { match: m, riskLevel: level, selection: riskLevelData.main };
        })
        .filter((x): x is BetSlipItem => x !== null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [matches, perMatchRisk, groupRisk]
  );

  return (
    <div className="container">
      <div className="header">
        <h1>Porvabet — Analisi pre-match</h1>
        <button className="refresh-btn" onClick={handleRefreshAll} disabled={refreshing}>
          {refreshing ? "Aggiornamento in corso…" : "AGGIORNA ANALISI"}
        </button>
      </div>

      <div className="synthetic-banner">
        I dati mostrati dipendono da cosa è stato ingerito in questo ambiente (vedi DATA_SOURCES.md).
        Se è stato eseguito <code>scripts/seed_dev_fixture.py</code>, si tratta di dati SINTETICI di
        test — non partite reali. La colonna quota mostra il bookmaker effettivamente disponibile nei
        dati ingeriti (es. media di mercato storica), non necessariamente ePlay24: vedi DATA_SOURCES.md
        per lo stato reale dell'accesso a ePlay24.
      </div>

      <div className="controls" style={{ marginBottom: 16 }}>
        <label htmlFor="group-risk">RISCHIO GRUPPO: {groupRisk}</label>
        <input
          id="group-risk"
          className="risk-slider"
          type="range"
          min={1}
          max={10}
          value={groupRisk}
          onChange={(e) => handleGroupRiskChange(Number(e.target.value))}
        />
      </div>

      {loading && <p>Caricamento…</p>}
      {error && <p style={{ color: "#ef4444" }}>{error}</p>}

      {!loading && !error && (
        <div className="layout">
          <table>
            <thead>
              <tr>
                <th>Data/Ora</th>
                <th>Partita</th>
                <th>Risk</th>
                <th>Selezione</th>
                <th>Quota</th>
                <th>Probabilità</th>
                <th>Quota Modello</th>
                <th>Info</th>
                <th>Value</th>
                <th>🚨</th>
              </tr>
            </thead>
            <tbody>
              {matches.map((m) => {
                const level = effectiveRisk(m.id);
                const riskLevelData = m.risk_levels.find((rl) => rl.risk_level === level);
                if (!riskLevelData) return null;
                const sel = riskLevelData.main;
                return (
                  <tr key={m.id}>
                    <td>
                      <Link className="link-back" href={`/match/${m.id}`}>
                        {new Date(m.kickoff_utc).toLocaleString("it-IT", {
                          day: "2-digit",
                          month: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </Link>
                    </td>
                    <td>
                      <Link className="link-back" href={`/match/${m.id}`}>
                        {m.home_team} – {m.away_team}
                      </Link>
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <input
                        type="number"
                        min={1}
                        max={10}
                        className="risk-input-small"
                        value={level}
                        onChange={(e) => handleMatchRiskChange(m.id, Number(e.target.value))}
                      />
                      <div style={{ marginTop: 4 }}>
                        <RiskPill level={level} />
                      </div>
                    </td>
                    <td>
                      {sel.market_label}
                      <br />
                      <strong>{sel.outcome_label}</strong>
                    </td>
                    <td>
                      <span className="odds-cell">
                        {sel.bookmaker_odds !== null ? sel.bookmaker_odds.toFixed(2) : "n/d"}
                        <span className="odds-source">{sel.bookmaker_name ?? "n/d"}</span>
                      </span>
                    </td>
                    <td>{(sel.probability * 100).toFixed(1)}%</td>
                    <td>{sel.fair_odds.toFixed(2)}</td>
                    <td className="muted">{riskLevelData.risk_level ? sel.rationale.split(":")[0] : ""}</td>
                    <td className={sel.value === null ? "muted" : sel.value >= 0 ? "value-positive" : "value-negative"}>
                      {sel.value !== null ? `${(sel.value * 100).toFixed(1)}%` : "n/d"}
                    </td>
                    <td style={{ position: "relative" }} onClick={(e) => e.stopPropagation()}>
                      {sel.alert && sel.alert.level !== "NONE" && (
                        <>
                          <button
                            className="alert-btn"
                            onClick={() => setOpenAlertFor(openAlertFor === m.id ? null : m.id)}
                          >
                            🚨
                          </button>
                          {openAlertFor === m.id && (
                            <AlertPopover selection={sel} onClose={() => setOpenAlertFor(null)} />
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <BetSlip items={betSlipItems} />
        </div>
      )}
    </div>
  );
}
