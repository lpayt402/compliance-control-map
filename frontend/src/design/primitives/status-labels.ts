import type { ReadinessStatus } from "../../app/api/types";

export const statusLabels: Record<ReadinessStatus, string> = {
  NOT_ASSESSED: "Not assessed",
  GAP: "Gap",
  IN_PROGRESS: "In progress",
  PARTIAL: "Partial",
  READY: "Ready",
  NOT_APPLICABLE: "Not applicable",
};
