import type { MatchDetailOut, SelectionOut } from "../lib/types";

export interface BetSlipItem {
  match: MatchDetailOut;
  riskLevel: number;
  selection: SelectionOut;
}

export default function BetSlip({ items }: { items: BetSlipItem[] }) {
  // page.tsx only ever puts a selection with a real (non-null) bookmaker_odds
  // into `items` — an "n/d" main pick is excluded before it gets here, since a
  // real bet slip needs a real total quote. The `?? 1` is defensive only, in
  // case that invariant is ever broken upstream — never silently fabricates a
  // price, just skips that leg's contribution to the product.
  const totalOdds = items.reduce((acc, item) => acc * (item.selection.bookmaker_odds ?? 1), 1);
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
          <div>Quota: {item.selection.bookmaker_odds !== null ? item.selection.bookmaker_odds.toFixed(2) : "n/d"}</div>
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
