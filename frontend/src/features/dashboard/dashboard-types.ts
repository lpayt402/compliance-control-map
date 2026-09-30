import type { ReadinessStatus } from "../../app/api/types";

export interface DashboardQueueItem {
  id: string;
  external_id: string;
  title: string;
  domain: string;
  framework: string;
  framework_version: string;
  status_code: ReadinessStatus;
  due_date: string | null;
  updated_at: string;
  action_code?: string;
  changed_at?: string;
}

export interface DashboardData {
  counts: Record<ReadinessStatus, number>;
  total_requirements: number;
  denominator: number;
  ready_numerator: number;
  readiness_percentage: number;
  assessed_numerator: number;
  assessed_percentage: number;
  formula: string;
  missing_documentation_count: number;
  missing_evidence_count: number;
  missing_documentation: DashboardQueueItem[];
  missing_evidence: DashboardQueueItem[];
  overdue: DashboardQueueItem[];
  gaps: DashboardQueueItem[];
  recently_changed: DashboardQueueItem[];
  as_of: string;
}
