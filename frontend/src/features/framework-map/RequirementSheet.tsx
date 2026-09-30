import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api, RevisionConflict } from "../../app/api/client";
import type { ActivityRecord, PersonSummary, ReadinessStatus, RequirementSummary } from "../../app/api/types";
import { useOptionalSession } from "../../app/session/session-context";
import { formatActionCode } from "../../design/format";
import { StatusMark } from "../../design/primitives/StatusMark";
import { statusLabels } from "../../design/primitives/status-labels";
import { ControlPanel } from "./ControlPanel";
import { AssistPanel, type AssistanceResourceDraft } from "./AssistPanel";
import { EntityResources } from "./EntityResources";

type Applicability = RequirementSummary["assessment"]["applicability"];
type TabName = "Overview" | "Controls" | "Resources" | "Assist" | "Activity";

interface Draft {
  status_code: ReadinessStatus;
  applicability: Applicability;
  owner_user_id: string | null;
  assignee_user_id: string | null;
  due_date: string | null;
  implementation_notes: string;
  tags: string;
  revision: number;
}

function draftFrom(requirement: RequirementSummary): Draft {
  return {
    status_code: requirement.assessment.status_code,
    applicability: requirement.assessment.applicability,
    owner_user_id: requirement.assessment.owner?.id ?? null,
    assignee_user_id: requirement.assessment.assignee?.id ?? null,
    due_date: requirement.assessment.due_date,
    implementation_notes: requirement.assessment.implementation_notes,
    tags: requirement.assessment.tags.join(", "),
    revision: requirement.assessment.revision,
  };
}

function ActivityList({ requirementId }: { requirementId: string }) {
  const path = "activity";
  const { data = [], isLoading, isError } = useQuery({
    queryKey: ["requirement-related", requirementId, path],
    queryFn: () => api.get<ActivityRecord[]>(`/requirements/${requirementId}/${path}`),
  });

  if (isLoading) return <p className="sheet-empty">Loading activity…</p>;
  if (isError) return <p className="sheet-empty sheet-empty--error">This section could not be loaded.</p>;
  if (data.length === 0) return <p className="sheet-empty">No activity recorded.</p>;
  return (
    <ul className="related-list">
      {data.map((item) => {
        return (
        <li key={item.id}>
          <strong>{formatActionCode(item.action_code)}</strong>
          <p>{item.actor_display_name ?? "System"} · {new Date(item.created_at).toLocaleString()}</p>
          {item.change_summary ? <small>{item.change_summary}</small> : null}
        </li>
        );
      })}
    </ul>
  );
}

function RequirementForm({
  requirement,
  frameworkSlug,
  canEdit,
  onDirtyChange,
  suggestion,
  onSuggestionApplied,
}: {
  requirement: RequirementSummary;
  frameworkSlug: string;
  canEdit: boolean;
  onDirtyChange: (dirty: boolean) => void;
  suggestion: { id: number; text: string } | null;
  onSuggestionApplied: () => void;
}) {
  const queryClient = useQueryClient();
  const { data: directory = [] } = useQuery({
    queryKey: ["user-directory"],
    queryFn: () => api.get<Array<Pick<PersonSummary, "id" | "display_name">>>("/users/directory"),
  });
  const [baseline, setBaseline] = useState(() => draftFrom(requirement));
  const [draft, setDraft] = useState(() => ({
    ...draftFrom(requirement),
    ...(suggestion ? { implementation_notes: suggestion.text } : {}),
  }));
  const [saveState, setSaveState] = useState<"idle" | "saved" | "conflict">("idle");

  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(baseline), [baseline, draft]);
  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange]);
  const mutation = useMutation({
    mutationFn: () => api.patch<RequirementSummary>(`/requirements/${requirement.id}/assessment`, {
      status_code: draft.status_code,
      applicability: draft.applicability,
      owner_user_id: draft.owner_user_id,
      assignee_user_id: draft.assignee_user_id,
      due_date: draft.due_date || null,
      implementation_notes: draft.implementation_notes,
      tags: draft.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      revision: draft.revision,
    }),
    onSuccess: (updated) => {
      const next = draftFrom(updated);
      setBaseline(next);
      setDraft(next);
      setSaveState("saved");
      queryClient.setQueryData<RequirementSummary[]>(["requirements", frameworkSlug], (current) =>
        current?.map((item) => item.id === updated.id ? updated : item),
      );
    },
    onError: (error) => setSaveState(error instanceof RevisionConflict ? "conflict" : "idle"),
  });

  function changeStatus(status: ReadinessStatus): void {
    setSaveState("idle");
    setDraft((current) => ({
      ...current,
      status_code: status,
      applicability: status === "NOT_APPLICABLE"
        ? "NOT_APPLICABLE"
        : current.applicability === "NOT_APPLICABLE" ? "APPLICABLE" : current.applicability,
    }));
  }

  function changeApplicability(applicability: Applicability): void {
    setSaveState("idle");
    setDraft((current) => ({
      ...current,
      applicability,
      status_code: applicability === "NOT_APPLICABLE"
        ? "NOT_APPLICABLE"
        : current.status_code === "NOT_APPLICABLE" ? "NOT_ASSESSED" : current.status_code,
    }));
  }

  return (
    <form className="requirement-form" onSubmit={(event) => { event.preventDefault(); if (canEdit) mutation.mutate(); }}>
      <div className="sheet-field-row">
        <label>
          Readiness
          <select disabled={!canEdit} value={draft.status_code} onChange={(event) => changeStatus(event.target.value as ReadinessStatus)}>
            {(Object.keys(statusLabels) as ReadinessStatus[]).map((status) => (
              <option key={status} value={status}>{statusLabels[status]}</option>
            ))}
          </select>
        </label>
        <label>
          Applicability
          <select disabled={!canEdit} value={draft.applicability} onChange={(event) => changeApplicability(event.target.value as Applicability)}>
            <option value="UNDETERMINED">Undetermined</option>
            <option value="APPLICABLE">Applicable</option>
            <option value="NOT_APPLICABLE">Not applicable</option>
          </select>
        </label>
      </div>
      <div className="sheet-field-row">
        <label>
          Owner
          <select
            disabled={!canEdit}
            value={draft.owner_user_id ?? ""}
            onChange={(event) => setDraft({ ...draft, owner_user_id: event.target.value || null })}
          >
            <option value="">Unassigned</option>
            {directory.map((person) => <option key={person.id} value={person.id}>{person.display_name}</option>)}
            {requirement.assessment.owner && !directory.some((person) => person.id === requirement.assessment.owner?.id) ? <option value={requirement.assessment.owner.id}>{requirement.assessment.owner.display_name}</option> : null}
          </select>
        </label>
        <label>
          Assignee
          <select
            disabled={!canEdit}
            value={draft.assignee_user_id ?? ""}
            onChange={(event) => setDraft({ ...draft, assignee_user_id: event.target.value || null })}
          >
            <option value="">Unassigned</option>
            {directory.map((person) => <option key={person.id} value={person.id}>{person.display_name}</option>)}
            {requirement.assessment.assignee && !directory.some((person) => person.id === requirement.assessment.assignee?.id) ? <option value={requirement.assessment.assignee.id}>{requirement.assessment.assignee.display_name}</option> : null}
          </select>
        </label>
      </div>
      <label>
        Due date
        <input
          disabled={!canEdit}
          type="date"
          value={draft.due_date ?? ""}
          onChange={(event) => setDraft({ ...draft, due_date: event.target.value || null })}
        />
      </label>
      <label>
        Tags
        <input
          disabled={!canEdit}
          value={draft.tags}
          onChange={(event) => setDraft({ ...draft, tags: event.target.value })}
          placeholder="access, quarterly, people"
        />
      </label>
      <label>
        Implementation notes
        <textarea
          disabled={!canEdit}
          rows={9}
          value={draft.implementation_notes}
          onChange={(event) => setDraft({ ...draft, implementation_notes: event.target.value })}
          placeholder="How does the organization satisfy this requirement?"
        />
      </label>
      {saveState === "conflict" ? (
        <div className="conflict-note" role="alert">
          <strong>Someone else changed this requirement.</strong>
          <p>Your draft is still here. Reload the current record, then reapply the parts you want.</p>
          <button type="button" onClick={() => window.location.reload()}>Reload current</button>
        </div>
      ) : null}
      {mutation.isError && saveState !== "conflict" ? (
        <p className="form-error" role="alert">The change was not saved. Check the fields and try again.</p>
      ) : null}
      {canEdit ? <footer className="sheet-savebar">
        <span aria-live="polite">{dirty ? "Unsaved" : saveState === "saved" ? "Saved" : "No pending changes"}</span>
        <button disabled={!dirty || mutation.isPending} type="button" onClick={() => { setDraft(baseline); setSaveState("idle"); onSuggestionApplied(); }}>
          Cancel edits
        </button>
        <button className="primary-button" disabled={!dirty || mutation.isPending} type="submit">
          {mutation.isPending ? "Saving…" : "Save changes"}
        </button>
      </footer> : <p className="viewer-note">Viewer access · assessment fields are read only.</p>}
    </form>
  );
}

export function RequirementSheet({
  open,
  onOpenChange,
  requirement,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  requirement: RequirementSummary;
}) {
  const [tab, setTab] = useState<TabName>("Overview");
  const [dirty, setDirty] = useState(false);
  const [discardToken, setDiscardToken] = useState(0);
  const [implementationSuggestion, setImplementationSuggestion] = useState<{ id: number; text: string } | null>(null);
  const [resourceSuggestion, setResourceSuggestion] = useState<AssistanceResourceDraft | null>(null);
  const session = useOptionalSession();
  const canEdit = session?.user?.role !== "VIEWER";
  const tabs: TabName[] = canEdit ? ["Overview", "Controls", "Resources", "Assist", "Activity"] : ["Overview", "Controls", "Resources", "Activity"];
  const clearImplementationSuggestion = useCallback(() => setImplementationSuggestion(null), []);
  const clearResourceSuggestion = useCallback(() => setResourceSuggestion(null), []);

  function changeTab(next: TabName): void {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    if (dirty) {
      setImplementationSuggestion(null);
      setDiscardToken((current) => current + 1);
    }
    setTab(next);
  }

  function requestOpenChange(nextOpen: boolean): void {
    if (!nextOpen && dirty && !window.confirm("Discard unsaved changes?")) return;
    onOpenChange(nextOpen);
  }

  return (
    <Dialog.Root open={open} onOpenChange={requestOpenChange}>
      <Dialog.Portal>
        <div aria-hidden="true" className="dialog-scrim requirement-sheet-scrim" />
        <Dialog.Content className="requirement-sheet" onEscapeKeyDown={(event) => {
          if (dirty && !window.confirm("Discard unsaved changes?")) event.preventDefault();
        }} onInteractOutside={(event) => { if (dirty) event.preventDefault(); }}>
          <header className="sheet-header">
            <div>
              <p className="eyebrow">{requirement.framework.name} / {requirement.domain.name}</p>
              <Dialog.Title>{requirement.external_id} · {requirement.title}</Dialog.Title>
              <Dialog.Description className="visually-hidden">
                Assess and document {requirement.external_id}, {requirement.title}.
              </Dialog.Description>
              <div className="sheet-status-line">
                <StatusMark status={requirement.assessment.status_code} />
                <span>Revision {requirement.assessment.revision}</span>
              </div>
            </div>
            <Dialog.Close className="sheet-close" aria-label="Close requirement details">×</Dialog.Close>
          </header>
          <nav className="sheet-tabs" aria-label="Requirement sections" role="tablist">
            {tabs.map((item) => (
              <button
                aria-controls={`sheet-panel-${item.toLowerCase()}`}
                aria-selected={tab === item}
                id={`sheet-tab-${item.toLowerCase()}`}
                key={item}
                onClick={() => changeTab(item)}
                role="tab"
                tabIndex={tab === item ? 0 : -1}
                type="button"
              >
                {item}
              </button>
            ))}
          </nav>
          <div
            aria-labelledby={`sheet-tab-${tab.toLowerCase()}`}
            className="sheet-panel"
            id={`sheet-panel-${tab.toLowerCase()}`}
            role="tabpanel"
          >
            <div hidden={tab !== "Overview"}>
                <section className="requirement-brief">
                  <p className="eyebrow">Requirement source text</p>
                  <p>{requirement.summary}</p>
                  {requirement.guidance ? <aside><strong>Field guidance</strong>{requirement.guidance}</aside> : null}
                </section>
                <RequirementForm canEdit={canEdit} frameworkSlug={requirement.framework.slug} key={`${requirement.id}:${discardToken}:${implementationSuggestion?.id ?? "none"}`} onDirtyChange={setDirty} onSuggestionApplied={clearImplementationSuggestion} requirement={requirement} suggestion={implementationSuggestion} />
            </div>
            {tab === "Controls" ? <ControlPanel requirementId={requirement.id} canEdit={canEdit} /> : null}
            {tab === "Resources" ? <EntityResources canEdit={canEdit} entityId={requirement.id} entityType="requirement" initialDraft={resourceSuggestion} onDraftApplied={clearResourceSuggestion} /> : null}
            {tab === "Assist" && canEdit ? <AssistPanel canEdit entityId={requirement.id} entityType="requirement" onImplementationDraft={(text) => { setImplementationSuggestion({ id: Date.now(), text }); setTab("Overview"); }} onResourceDraft={(nextDraft) => { setResourceSuggestion(nextDraft); setTab("Resources"); }} /> : null}
            {tab === "Activity" ? <ActivityList requirementId={requirement.id} /> : null}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
