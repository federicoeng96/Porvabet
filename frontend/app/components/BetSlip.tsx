import type { MatchDetailOut, SelectionOut } from "../lib/types";

export interface BetSlipItem {
  match: MatchDetailOut;
  riskLevel: number;
  selection: SelectionOut;
}

export default function BetSlip({ items }: { items: BetSlipItem[] }) {
  const totalOdds = items.reduce((acc, item) => acc * item.selection.bookmaker_odds, 1);
  return (
    <aside className="betslip">
      <h2>Schedina automatica</h2>
      {items.length === 0 && <p className="muted">Nessuna selezione disponibile.</p>}
      {items.map((item) => (
        <div className="betslip-item" key={item.match.id}>
          <div className="match-name">
            {item.match.home_team} – {item.match.away_team}
          </div>
          <div className="muted">
            Risk {item.riskLevel} · {item.selection.market_label} {item.selection.outcome_label}
          </div>
          <div>Quota: {item.selection.bookmaker_odds.toFixed(2)}</div>
        </div>
      ))}
      {items.length > 0 && (
        <div className="betslip-total">
          <span>Quota totale</span>
          <span>{totalOdds.toFixed(2)}</span>
        </div>
      )}
    </aside>
  );
}
