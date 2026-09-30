import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { api } from "../../app/api/client";
import type { ReadinessStatus, RequirementSummary } from "../../app/api/types";
import { useSession } from "../../app/session/session-context";
import { statusLabels } from "../../design/primitives/status-labels";
import { AssessmentTable } from "./AssessmentTable";

export function TrackerPage() {
  const { user } = useSession();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ReadinessStatus | "">("");
  const { data = [], isLoading, isError } = useQuery({
    queryKey: ["requirements", "all"],
    queryFn: () => api.get<RequirementSummary[]>("/requirements?limit=200"),
  });
  const filtered = useMemo(() => data.filter((item) => {
    const needle = search.trim().toLowerCase();
    return (!needle || `${item.external_id} ${item.title}`.toLowerCase().includes(needle)) && (!status || item.assessment.status_code === status);
  }), [data, search, status]);
  const canEdit = user?.role !== "VIEWER";

  return (
    <section className="tracker-page">
      <header className="operational-heading"><div><p className="eyebrow">Working register</p><h1>Tracker</h1></div><p>Sort the work. Move it forward. Keep the framework map honest.</p></header>
      <div className="tracker-tools">
        <label>Search<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Identifier or title" /></label>
        <label>Status<select value={status} onChange={(event) => setStatus(event.target.value as ReadinessStatus | "")}><option value="">All statuses</option>{(Object.keys(statusLabels) as ReadinessStatus[]).map((code) => <option key={code} value={code}>{statusLabels[code]}</option>)}</select></label>
        <span role="status">{filtered.length} requirement{filtered.length === 1 ? "" : "s"}</span>
      </div>
      {isLoading ? <p className="operational-state">Loading the working register…</p> : isError ? <p className="operational-state">The tracker could not be loaded.</p> : <AssessmentTable requirements={filtered} canEdit={canEdit} />}
    </section>
  );
}
