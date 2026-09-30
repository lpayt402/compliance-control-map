import type { ReadinessStatus } from "../../app/api/types";

export interface FrameworkFilterState {
  search: string;
  statuses: ReadinessStatus[];
  domain: string;
  applicability: string;
  owner: string;
  assignee: string;
  tag: string;
}

export const emptyFrameworkFilters: FrameworkFilterState = {
  search: "",
  statuses: [],
  domain: "",
  applicability: "",
  owner: "",
  assignee: "",
  tag: "",
};
