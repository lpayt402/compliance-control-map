import type { ReadinessStatus } from "../../app/api/types";
import { StatusMark } from "../../design/primitives/StatusMark";
import type { DashboardData } from "./dashboard-types";

const statuses: ReadinessStatus[] = ["READY", "PARTIAL", "IN_PROGRESS", "GAP", "NOT_ASSESSED", "NOT_APPLICABLE"];

export function ReadinessLedger({ dashboard }: { dashboard: DashboardData }) {
  return (
    <section className="readiness-ledger" aria-labelledby="readiness-heading">
      <div className="readiness-score">
        <p className="eyebrow">Readiness summary</p>
        <h2 id="readiness-heading">{dashboard.readiness_percentage}% ready</h2>
        <p>{dashboard.ready_numerator} Ready ÷ {dashboard.denominator} applicable requirements</p>
        <p className="formula-note">Not applicable is excluded from readiness.</p>
      </div>
      <div className="assessed-score">
        <strong>{dashboard.assessed_percentage}% assessed</strong>
        <span>{dashboard.assessed_numerator} of {dashboard.denominator} applicable requirements reviewed</span>
      </div>
      <dl className="status-ledger">
        {statuses.map((status) => (
          <div key={status}>
            <dt><StatusMark status={status} /></dt>
            <dd>{dashboard.counts[status]}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
