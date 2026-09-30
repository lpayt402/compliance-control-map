import { useQuery } from "@tanstack/react-query";

import { api } from "../../app/api/client";
import { ActionQueues } from "./ActionQueues";
import type { DashboardData } from "./dashboard-types";
import { ReadinessLedger } from "./ReadinessLedger";

export function DashboardPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.get<DashboardData>("/dashboard"),
  });

  return (
    <section className="dashboard-page">
      <header className="operational-heading">
        <div><p className="eyebrow">Workspace readiness</p><h1>Compliance Control Map</h1></div>
        <p>Where you are, what is missing, and what deserves attention next.</p>
      </header>
      {isLoading ? <section className="operational-state"><p>Loading readiness data…</p></section> : isError || !data ? <section className="operational-state"><p>The dashboard could not be loaded.</p><button onClick={() => void refetch()}>Try again</button></section> : <>
        <ReadinessLedger dashboard={data} />
        <div className="section-rule"><span>Action queues</span><time dateTime={data.as_of}>As of {new Date(data.as_of).toLocaleDateString()}</time></div>
        <ActionQueues dashboard={data} />
      </>}
    </section>
  );
}
