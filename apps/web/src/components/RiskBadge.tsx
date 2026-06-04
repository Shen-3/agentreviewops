import type { RiskLevel } from "../api/types";

export function RiskBadge({ level, label }: { level: RiskLevel; label: string }) {
  return <span className={`risk-badge risk-${level}`}>{label}</span>;
}

