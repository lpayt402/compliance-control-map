import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../../app/api/client";
import type { ReadinessStatus, RequirementSummary } from "../../app/api/types";
import { statusLabels } from "../../design/primitives/status-labels";

export function InlineStatusSelect({ requirement }: { requirement: RequirementSummary }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState(requirement.assessment.status_code);
  const mutation = useMutation({
    mutationFn: (next: ReadinessStatus) => api.patch<RequirementSummary>(`/requirements/${requirement.id}/assessment`, {
      status_code: next,
      applicability: next === "NOT_APPLICABLE" ? "NOT_APPLICABLE" : requirement.assessment.applicability === "NOT_APPLICABLE" ? "APPLICABLE" : requirement.assessment.applicability,
      revision: requirement.assessment.revision,
    }),
    onSuccess: (updated) => {
      setStatus(updated.assessment.status_code);
      void queryClient.invalidateQueries({ queryKey: ["requirements"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: () => setStatus(requirement.assessment.status_code),
  });

  return (
    <select
      aria-label={`Readiness for ${requirement.external_id}`}
      className={`inline-status inline-status--${status.toLowerCase()}`}
      disabled={mutation.isPending}
      value={status}
      onChange={(event) => {
        const next = event.target.value as ReadinessStatus;
        setStatus(next);
        mutation.mutate(next);
      }}
    >
      {(Object.keys(statusLabels) as ReadinessStatus[]).map((code) => <option key={code} value={code}>{statusLabels[code]}</option>)}
    </select>
  );
}
