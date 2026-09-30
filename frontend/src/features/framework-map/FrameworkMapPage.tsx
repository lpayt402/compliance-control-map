import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router";

import { api } from "../../app/api/client";
import type { RequirementSummary } from "../../app/api/types";
import { FrameworkFilters } from "./FrameworkFilters";
import { emptyFrameworkFilters, type FrameworkFilterState } from "./filter-state";
import { RequirementSheet } from "./RequirementSheet";
import { RequirementTile } from "./RequirementTile";

function matches(requirement: RequirementSummary, filters: FrameworkFilterState): boolean {
  const needle = filters.search.trim().toLocaleLowerCase();
  const searchable = [
    requirement.external_id,
    requirement.title,
    requirement.summary,
    requirement.assessment.implementation_notes,
    ...requirement.assessment.tags,
  ].join(" ").toLocaleLowerCase();
  return (
    (!needle || searchable.includes(needle)) &&
    (!filters.statuses.length || filters.statuses.includes(requirement.assessment.status_code)) &&
    (!filters.domain || requirement.domain.external_id === filters.domain) &&
    (!filters.applicability || requirement.assessment.applicability === filters.applicability) &&
    (!filters.owner || requirement.assessment.owner?.id === filters.owner) &&
    (!filters.assignee || requirement.assessment.assignee?.id === filters.assignee) &&
    (!filters.tag || requirement.assessment.tags.includes(filters.tag))
  );
}

function countLabel(count: number): string {
  return `${count} requirement${count === 1 ? "" : "s"} shown`;
}

export function FrameworkMapPage() {
  const { framework = "soc2" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<FrameworkFilterState>(emptyFrameworkFilters);
  const [activeId, setActiveId] = useState("");
  const buttonRefs = useRef(new Map<string, HTMLButtonElement>());
  const returnFocusId = useRef("");
  const { data: requirements = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["requirements", framework],
    queryFn: () => api.get<RequirementSummary[]>(`/requirements?framework=${encodeURIComponent(framework)}&limit=200`),
  });

  const visible = useMemo(() => requirements.filter((item) => matches(item, filters)), [requirements, filters]);
  const domains = useMemo(() => {
    const grouped = new Map<string, { name: string; requirements: RequirementSummary[] }>();
    for (const requirement of visible) {
      const current = grouped.get(requirement.domain.external_id);
      if (current) current.requirements.push(requirement);
      else grouped.set(requirement.domain.external_id, { name: requirement.domain.name, requirements: [requirement] });
    }
    return grouped;
  }, [visible]);

  const effectiveActiveId = visible.some((item) => item.external_id === activeId)
    ? activeId
    : visible[0]?.external_id ?? "";

  const selectedId = searchParams.get("requirement");
  const selected = requirements.find((item) => item.external_id === selectedId) ?? null;

  useEffect(() => {
    if (selected || !returnFocusId.current) return;
    const targetId = returnFocusId.current;
    returnFocusId.current = "";
    const frame = requestAnimationFrame(() => buttonRefs.current.get(targetId)?.focus());
    return () => cancelAnimationFrame(frame);
  }, [selected]);

  function openRequirement(requirement: RequirementSummary): void {
    returnFocusId.current = requirement.external_id;
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("requirement", requirement.external_id);
      return next;
    });
  }

  function closeRequirement(): void {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("requirement");
      return next;
    });
  }

  function moveFocus(currentId: string, key: string): void {
    const currentIndex = visible.findIndex((item) => item.external_id === currentId);
    if (currentIndex < 0 || visible.length === 0) return;
    let target = currentIndex;
    if (key === "ArrowRight" || key === "ArrowDown") target = Math.min(currentIndex + 1, visible.length - 1);
    else if (key === "ArrowLeft" || key === "ArrowUp") target = Math.max(currentIndex - 1, 0);
    else if (key === "Home") target = 0;
    else if (key === "End") target = visible.length - 1;
    else return;
    const targetRequirement = visible[target];
    if (!targetRequirement) return;
    const id = targetRequirement.external_id;
    setActiveId(id);
    buttonRefs.current.get(id)?.focus();
  }

  if (isLoading) return <section className="atlas-state"><p>Loading framework requirements…</p></section>;
  if (isError) return (
    <section className="atlas-state">
      <p>The framework could not be loaded.</p>
      <button onClick={() => void refetch()} type="button">Try again</button>
    </section>
  );

  const frameworkName = requirements[0]?.framework.name ?? framework;
  const version = requirements[0]?.framework.version;

  return (
    <section className="framework-map-page">
      <header className="atlas-heading">
        <div>
          <p className="eyebrow">Framework requirements {version ? `/ ${version}` : ""}</p>
          <h1>{frameworkName}</h1>
        </div>
        <p>Scan the terrain. Open a plate to assess, assign, document, and file proof.</p>
      </header>
      <FrameworkFilters
        filters={filters}
        requirements={requirements}
        onChange={setFilters}
        onReset={() => setFilters(emptyFrameworkFilters)}
      />
      <div className="atlas-count" role="status" aria-live="polite">{countLabel(visible.length)}</div>
      {visible.length === 0 ? (
        <div className="atlas-empty">
          <strong>No plates match that combination.</strong>
          <p>Clear a filter and the map will redraw itself. Tiny cartographer, big feelings.</p>
        </div>
      ) : (
        <div className="framework-atlas" aria-label={`${frameworkName} requirements`}>
          {[...domains].map(([domainId, domain]) => (
            <section className="framework-domain" key={domainId} aria-labelledby={`domain-${domainId}`}>
              <header>
                <span>{domainId}</span>
                <h2 id={`domain-${domainId}`}>{domain.name}</h2>
                <small>{domain.requirements.length}</small>
              </header>
              <div className="domain-plates">
                {domain.requirements.map((requirement) => (
                  <RequirementTile
                    active={requirement.external_id === effectiveActiveId}
                    buttonRef={(element) => {
                      if (element) buttonRefs.current.set(requirement.external_id, element);
                      else buttonRefs.current.delete(requirement.external_id);
                    }}
                    key={requirement.id}
                    onActivate={() => openRequirement(requirement)}
                    onKeyDown={(event) => {
                      if (["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"].includes(event.key)) {
                        event.preventDefault();
                        moveFocus(requirement.external_id, event.key);
                      }
                    }}
                    requirement={requirement}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
      {selected ? (
        <RequirementSheet key={selected.id} open onOpenChange={(open) => { if (!open) closeRequirement(); }} requirement={selected} />
      ) : null}
    </section>
  );
}
