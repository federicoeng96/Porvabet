"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import AlertPopover from "../../components/AlertPopover";
import RiskPill from "../../components/RiskPill";
import { analyzeMatch, getMatchDetail } from "../../lib/api";
import type { MatchDetailOut, SelectionOut } from "../../lib/types";

export default function MatchDetailPage() {
  const params = useParams<{ id: string }>();
  const matchId = Number(params.id);
  const [match, setMatch] = useState<MatchDetailOut | null>(null);
  const [riskLevel, setRiskLevel] = useState(5);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [openAlert, setOpenAlert] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    const detail = await getMatchDetail(matchId);
    setMatch(detail);
    setLoading(false);
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await analyzeMatch(matchId);
      await load();
    } finally {
      setRefreshing(false);
    }
  }

  if (loading || !match) return <div className="container">Caricamento…</div>;

  const current = match.risk_levels.find((rl) => rl.risk_level === riskLevel);

  function renderSelection(sel: SelectionOut, keySuffix: string, label: string) {
    return (
      <div className="detail-card" key={keySuffix}>
        <div className="muted">{label}</div>
        <div style={{ fontSize: 16, fontWeight: 700, margin: "4px 0" }}>
          {sel.market_label} — {sel.outcome_label}
        </div>
        <div>Probabilità modello: {(sel.probability * 100).toFixed(1)}%</div>
        <div>
          Quota bookmaker ({sel.bookmaker_name ?? "n/d"}): <strong>{sel.bookmaker_odds.toFixed(2)}</strong>
        </div>
        <div>Quota fair stimata: {sel.fair_odds.toFixed(2)}</div>
        <div>Valore/edge stimato: {(sel.value * 100).toFixed(1)}%</div>
        <div className="muted">Incertezza: {(sel.uncertainty * 100).toFixed(0)}%</div>
        <div className="muted">Confidence: {(sel.confidence * 100).toFixed(0)}%</div>
        <p className="muted">{sel.rationale}</p>
        {sel.alert && sel.alert.level !== "NONE" && (
          <div style={{ position: "relative" }}>
            <button className="alert-btn" onClick={() => setOpenAlert(openAlert === keySuffix ? null : keySuffix)}>
              🚨 dettagli alert
            </button>
            {openAlert === keySuffix && (
              <AlertPopover selection={sel} onClose={() => setOpenAlert(null)} />
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="container">
      <Link className="link-back" href="/">
        ← Torna alla tabella
      </Link>
      <div className="header" style={{ marginTop: 12 }}>
        <h1>
          {match.home_team} – {match.away_team}
        </h1>
        <button className="refresh-btn" onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? "Aggiornamento…" : "AGGIORNA ANALISI"}
        </button>
      </div>
      <p className="muted">
        {new Date(match.kickoff_utc).toLocaleString("it-IT")} · {match.competition_code} ·{" "}
        {match.computed_at ? `analisi calcolata il ${new Date(match.computed_at).toLocaleString("it-IT")}` : "nessuna analisi disponibile"}
      </p>

      <div className="controls" style={{ marginBottom: 16 }}>
        <label>Risk: {riskLevel}</label>
        <input
          className="risk-slider"
          type="range"
          min={1}
          max={10}
          value={riskLevel}
          onChange={(e) => setRiskLevel(Number(e.target.value))}
        />
        <RiskPill level={riskLevel} />
      </div>

      {!current && <p>Nessuna selezione disponibile per questo livello di rischio.</p>}
      {current && (
        <>
          {renderSelection(current.main, "main", "Selezione principale")}
          {current.alternatives.map((alt, i) => renderSelection(alt, `alt-${i}`, `Alternativa ${i + 1}`))}
        </>
      )}

      {match.additional_estimates.length > 0 && (
        <>
          <h2 style={{ fontSize: 14, marginTop: 24 }}>Stime senza quota reale (Value/Alert: n/d)</h2>
          {Object.entries(
            match.additional_estimates.reduce<Record<string, typeof match.additional_estimates>>(
              (acc, est) => {
                const key = `${est.market_category}:${est.line ?? ""}`;
                (acc[key] ??= []).push(est);
                return acc;
              },
              {}
            )
          ).map(([key, ests]) => (
            <div className="detail-card" key={key}>
              <div style={{ fontSize: 16, fontWeight: 700, margin: "4px 0" }}>
                {ests[0].market_label}
                {ests[0].line != null ? ` (linea ${ests[0].line})` : ""}
              </div>
              {ests.map((est) => (
                <div key={est.outcome_label}>
                  {est.outcome_label}: {(est.probability * 100).toFixed(1)}% (quota fair{" "}
                  {est.fair_odds.toFixed(2)}) — Value/Alert: <strong>n/d</strong>
                </div>
              ))}
              <p className="muted" style={{ fontStyle: "italic" }}>
                {ests[0].note}
              </p>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
