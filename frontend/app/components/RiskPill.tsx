export function riskColor(level: number): string {
  if (level <= 3) return "#22c55e";
  if (level <= 7) return "#eab308";
  return "#ef4444";
}

export default function RiskPill({ level }: { level: number }) {
  return (
    <span className="risk-pill" style={{ background: riskColor(level) }}>
      {level}
    </span>
  );
}
