import type { ReadinessStatus } from "../../app/api/types";
import { statusLabels } from "./status-labels";

export function StatusMark({ status, compact = false }: { status: ReadinessStatus; compact?: boolean }) {
  return (
    <span className={`status-mark status-mark--${status.toLowerCase()}${compact ? " status-mark--compact" : ""}`}>
      <span className="status-glyph" aria-hidden="true" />
      <span>{statusLabels[status]}</span>
    </span>
  );
}
