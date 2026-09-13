"use client";

import type { AlertOut, SelectionOut } from "../lib/types";

// Wording calibrated against the real 10-season backtest (see
// BACKTEST_SPEC.md "Calibrazione soglie alert su dati reali"): a bigger
// model-vs-market gap does NOT mean the model is more likely right — ROI
// gets steadily worse as the gap grows. STRONG is a caution flag ("il
// modello si discosta molto dal book, storicamente un segnale che il
// modello ha più spesso torto"), deliberately never framed as an
// opportunity or "mispricing".
const LEVEL_LABEL: Record<AlertOut["level"], string> = {
  NONE: "",
  INTERESTING: "Discrepanza interessante",
  STRONG: "Discrepanza marcata (cautela: storicamente il modello ha più spesso torto qui)",
};

export default function AlertPopover({
  selection,
  onClose,
}: {
  selection: SelectionOut;
  onClose: () => void;
}) {
  const alert = selection.alert;
  if (!alert) return null;
  return (
    <div className="popover" onClick={(e) => e.stopPropagation()}>
      <div className="popover-title">{LEVEL_LABEL[alert.level]}</div>
      <div>
        <strong>{selection.market_label}</strong> — {selection.outcome_label}
      </div>
      <div className="muted">Probabilità modello: {(selection.probability * 100).toFixed(1)}%</div>
      <div className="muted">
        Quota bookmaker ({selection.bookmaker_name ?? "n/d"}):{" "}
        {selection.bookmaker_odds !== null ? selection.bookmaker_odds.toFixed(2) : "n/d"}
      </div>
      <div className="muted">Quota fair stimata: {selection.fair_odds.toFixed(2)}</div>
      <div className="muted">
        Valore/edge stimato: {selection.value !== null ? `${(selection.value * 100).toFixed(1)}%` : "n/d"}
      </div>
      <p style={{ marginTop: 8 }}>{alert.explanation}</p>
      <p className="muted" style={{ fontStyle: "italic" }}>
        Nota: questa è una stima del modello, non una garanzia che la quota sia sbagliata.
      </p>
      <button className="refresh-btn" style={{ marginTop: 8 }} onClick={onClose}>
        Chiudi
      </button>
    </div>
  );
}
