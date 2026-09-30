import type { ReadinessStatus, RequirementSummary } from "../../app/api/types";
import { statusLabels } from "../../design/primitives/status-labels";
import type { FrameworkFilterState } from "./filter-state";

const readinessStatuses = Object.keys(statusLabels) as ReadinessStatus[];

function uniquePeople(
  requirements: RequirementSummary[],
  field: "owner" | "assignee",
): Array<{ id: string; label: string }> {
  const people = new Map<string, string>();
  for (const requirement of requirements) {
    const person = requirement.assessment[field];
    if (person) people.set(person.id, person.display_name);
  }
  return [...people].map(([id, label]) => ({ id, label }));
}

export function FrameworkFilters({
  filters,
  requirements,
  onChange,
  onReset,
}: {
  filters: FrameworkFilterState;
  requirements: RequirementSummary[];
  onChange: (next: FrameworkFilterState) => void;
  onReset: () => void;
}) {
  const domains = [...new Map(requirements.map((item) => [item.domain.external_id, item.domain.name]))];
  const tags = [...new Set(requirements.flatMap((item) => item.assessment.tags))].sort();
  const owners = uniquePeople(requirements, "owner");
  const assignees = uniquePeople(requirements, "assignee");
  const hasFilters = Object.values(filters).some((value) =>
    Array.isArray(value) ? value.length > 0 : Boolean(value),
  );

  function toggleStatus(status: ReadinessStatus): void {
    const statuses = filters.statuses.includes(status)
      ? filters.statuses.filter((candidate) => candidate !== status)
      : [...filters.statuses, status];
    onChange({ ...filters, statuses });
  }

  return (
    <section className="atlas-filters" aria-label="Framework filters">
      <div className="atlas-search">
        <label htmlFor="atlas-search">Find a requirement</label>
        <input
          id="atlas-search"
          onChange={(event) => onChange({ ...filters, search: event.target.value })}
          placeholder="Identifier, title, note, or tag"
          type="search"
          value={filters.search}
        />
      </div>
      <fieldset className="status-filter">
        <legend>Status</legend>
        <div>
          {readinessStatuses.map((status) => (
            <label key={status}>
              <input
                checked={filters.statuses.includes(status)}
                onChange={() => toggleStatus(status)}
                type="checkbox"
              />
              <span className={`filter-glyph filter-glyph--${status.toLowerCase()}`} aria-hidden="true" />
              {statusLabels[status]}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="atlas-filter-selects">
        <label>
          Domain
          <select
            onChange={(event) => onChange({ ...filters, domain: event.target.value })}
            value={filters.domain}
          >
            <option value="">All domains</option>
            {domains.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
        </label>
        <label>
          Applicability
          <select
            onChange={(event) => onChange({ ...filters, applicability: event.target.value })}
            value={filters.applicability}
          >
            <option value="">All</option>
            <option value="UNDETERMINED">Undetermined</option>
            <option value="APPLICABLE">Applicable</option>
            <option value="NOT_APPLICABLE">Not applicable</option>
          </select>
        </label>
        <label>
          Owner
          <select onChange={(event) => onChange({ ...filters, owner: event.target.value })} value={filters.owner}>
            <option value="">Anyone</option>
            {owners.map((person) => <option key={person.id} value={person.id}>{person.label}</option>)}
          </select>
        </label>
        <label>
          Assignee
          <select onChange={(event) => onChange({ ...filters, assignee: event.target.value })} value={filters.assignee}>
            <option value="">Anyone</option>
            {assignees.map((person) => <option key={person.id} value={person.id}>{person.label}</option>)}
          </select>
        </label>
        <label>
          Tag
          <select onChange={(event) => onChange({ ...filters, tag: event.target.value })} value={filters.tag}>
            <option value="">Any tag</option>
            {tags.map((tag) => <option key={tag} value={tag}>{tag}</option>)}
          </select>
        </label>
      </div>
      <button className="text-button" disabled={!hasFilters} onClick={onReset} type="button">
        Clear filters
      </button>
    </section>
  );
}
