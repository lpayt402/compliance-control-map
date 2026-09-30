import { Link } from "react-router";

import type { DashboardQueueItem } from "./dashboard-types";

function Queue({ title, count, items, empty }: { title: string; count: number; items: DashboardQueueItem[]; empty: string }) {
  return (
    <section className="action-queue">
      <header><h3>{title}</h3><span>{count}</span></header>
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={`${title}-${item.id}`}>
              <Link to={`/frameworks/${item.framework}/map?requirement=${encodeURIComponent(item.external_id)}`}>
                <strong>{item.external_id}</strong><span>{item.title}</span>
              </Link>
              {item.due_date ? <time dateTime={item.due_date}>Due {item.due_date}</time> : null}
            </li>
          ))}
        </ul>
      ) : <p>{empty}</p>}
    </section>
  );
}

export function ActionQueues({ dashboard }: { dashboard: import("./dashboard-types").DashboardData }) {
  return (
    <div className="action-queues">
      <Queue title="Gaps" count={dashboard.gaps.length} items={dashboard.gaps} empty="No open gaps. Suspiciously peaceful." />
      <Queue title="Overdue" count={dashboard.overdue.length} items={dashboard.overdue} empty="Nothing overdue." />
      <Queue title="No documentation" count={dashboard.missing_documentation_count} items={dashboard.missing_documentation} empty="Every applicable requirement has document coverage." />
      <Queue title="No evidence" count={dashboard.missing_evidence_count} items={dashboard.missing_evidence} empty="Every applicable requirement has evidence coverage." />
      <Queue title="Recently changed" count={dashboard.recently_changed.length} items={dashboard.recently_changed} empty="No recent changes yet." />
    </div>
  );
}
