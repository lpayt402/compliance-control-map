import { useMemo, useState } from "react";

import type { RequirementSummary } from "../../app/api/types";
import { StatusMark } from "../../design/primitives/StatusMark";
import { RequirementSheet } from "../framework-map/RequirementSheet";
import { InlineStatusSelect } from "./InlineStatusSelect";

type SortKey = "external_id" | "title" | "status" | "owner" | "assignee" | "due_date" | "last_updated";
type SortDirection = "ascending" | "descending";

function valueFor(requirement: RequirementSummary, key: SortKey): string {
  if (key === "status") return requirement.assessment.status_code;
  if (key === "owner") return requirement.assessment.owner?.display_name ?? "";
  if (key === "assignee") return requirement.assessment.assignee?.display_name ?? "";
  if (key === "due_date") return requirement.assessment.due_date ?? "9999-12-31";
  return requirement[key];
}

function SortHeader({ label, sortKey, activeKey, direction, onSort }: { label: string; sortKey: SortKey; activeKey: SortKey; direction: SortDirection; onSort: (key: SortKey) => void }) {
  const active = activeKey === sortKey;
  return (
    <th aria-sort={active ? direction : "none"} scope="col">
      <button aria-label={`Sort by ${label.toLowerCase()}`} onClick={() => onSort(sortKey)} type="button">
        {label}<span aria-hidden="true">{active ? direction === "ascending" ? " ↑" : " ↓" : " ↕"}</span>
      </button>
    </th>
  );
}

export function AssessmentTable({ requirements, canEdit }: { requirements: RequirementSummary[]; canEdit: boolean }) {
  const [sortKey, setSortKey] = useState<SortKey>("external_id");
  const [direction, setDirection] = useState<SortDirection>("ascending");
  const [selected, setSelected] = useState<RequirementSummary | null>(null);
  const sorted = useMemo(() => [...requirements].sort((left, right) => {
    const comparison = valueFor(left, sortKey).localeCompare(valueFor(right, sortKey), undefined, { numeric: true });
    return direction === "ascending" ? comparison : -comparison;
  }), [requirements, sortKey, direction]);

  function sort(key: SortKey): void {
    if (key === sortKey) setDirection((current) => current === "ascending" ? "descending" : "ascending");
    else { setSortKey(key); setDirection("ascending"); }
  }

  return (
    <>
      <div className="tracker-table-wrap">
        <table className="assessment-table" aria-label="Requirement assessment tracker">
          <caption>Requirement assessment tracker</caption>
          <thead><tr>
            <SortHeader label="Identifier" sortKey="external_id" activeKey={sortKey} direction={direction} onSort={sort} />
            <SortHeader label="Title" sortKey="title" activeKey={sortKey} direction={direction} onSort={sort} />
            <SortHeader label="Status" sortKey="status" activeKey={sortKey} direction={direction} onSort={sort} />
            <SortHeader label="Owner" sortKey="owner" activeKey={sortKey} direction={direction} onSort={sort} />
            <SortHeader label="Assignee" sortKey="assignee" activeKey={sortKey} direction={direction} onSort={sort} />
            <SortHeader label="Due date" sortKey="due_date" activeKey={sortKey} direction={direction} onSort={sort} />
            <th scope="col">Documents</th><th scope="col">Evidence</th>
            <SortHeader label="Last updated" sortKey="last_updated" activeKey={sortKey} direction={direction} onSort={sort} />
          </tr></thead>
          <tbody>
            {sorted.map((requirement) => (
              <tr key={requirement.id}>
                <th scope="row"><button className="table-detail-button" onClick={() => setSelected(requirement)}>{requirement.external_id}</button></th>
                <td>{requirement.title}</td>
                <td>{canEdit ? <InlineStatusSelect requirement={requirement} /> : <StatusMark status={requirement.assessment.status_code} compact />}</td>
                <td>{requirement.assessment.owner?.display_name ?? "—"}</td>
                <td>{requirement.assessment.assignee?.display_name ?? "—"}</td>
                <td>{requirement.assessment.due_date ?? "—"}</td>
                <td>{requirement.document_count}</td><td>{requirement.evidence_count}</td>
                <td><time dateTime={requirement.last_updated}>{new Date(requirement.last_updated).toLocaleDateString()}</time></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selected ? <RequirementSheet key={selected.id} open onOpenChange={(open) => { if (!open) setSelected(null); }} requirement={selected} /> : null}
    </>
  );
}
