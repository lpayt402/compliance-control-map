import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";

import { api, RevisionConflict } from "../../app/api/client";
import type {
  ActivityRecord,
  ControlRecord,
  PersonSummary,
} from "../../app/api/types";
import { formatActionCode } from "../../design/format";
import { AssistPanel, type AssistanceResourceDraft } from "./AssistPanel";
import { EntityResources } from "./EntityResources";

type ControlTab = "Overview" | "Resources" | "Assist" | "Activity";

interface ControlDraft {
  code: string;
  name: string;
  description: string;
  status_code: ControlRecord["status_code"];
  owner_user_id: string | null;
  implementation_notes: string;
  tags: string;
  revision: number;
}

interface ControlDetailProps {
  canEdit: boolean;
  controlId: string;
  onBack: () => void;
  onRemoved?: () => void;
  requirementId?: string;
}

function draftFrom(control: ControlRecord): ControlDraft {
  return {
    code: control.code,
    name: control.name,
    description: control.description,
    status_code: control.status_code,
    owner_user_id: control.owner?.id ?? null,
    implementation_notes: control.implementation_notes,
    tags: control.tags.join(", "),
    revision: control.revision,
  };
}

export function ControlDetail({
  canEdit,
  controlId,
  onBack,
  onRemoved,
  requirementId,
}: ControlDetailProps) {
  const controlQuery = useQuery({
    queryKey: ["control", controlId],
    queryFn: () => api.get<ControlRecord>(`/controls/${controlId}`),
  });
  if (controlQuery.isError) return <p className="form-error" role="alert">Control details could not be loaded.</p>;
  if (controlQuery.isLoading || !controlQuery.data) return <p className="resource-state">Loading control details…</p>;
  return (
    <LoadedControlDetail
      canEdit={canEdit}
      control={controlQuery.data}
      controlId={controlId}
      key={`${controlQuery.data.id}:${controlQuery.data.revision}`}
      onBack={onBack}
      onRemoved={onRemoved}
      requirementId={requirementId}
    />
  );
}

function LoadedControlDetail({
  canEdit,
  control,
  controlId,
  onBack,
  onRemoved,
  requirementId,
}: ControlDetailProps & { control: ControlRecord }) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<ControlTab>("Overview");
  const [baseline, setBaseline] = useState<ControlDraft>(() => draftFrom(control));
  const [draft, setDraft] = useState<ControlDraft>(() => draftFrom(control));
  const [saveState, setSaveState] = useState<"idle" | "saved" | "conflict">("idle");
  const [resourceSuggestion, setResourceSuggestion] = useState<AssistanceResourceDraft | null>(null);
  const clearResourceSuggestion = useCallback(() => setResourceSuggestion(null), []);
  const directoryQuery = useQuery({
    queryKey: ["user-directory"],
    queryFn: () => api.get<Array<Pick<PersonSummary, "id" | "display_name">>>("/users/directory"),
  });
  const activityQuery = useQuery({
    queryKey: ["control", controlId, "activity"],
    queryFn: () => api.get<ActivityRecord[]>(`/controls/${controlId}/activity`),
    enabled: tab === "Activity",
  });
  const dirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(baseline),
    [baseline, draft],
  );
  const save = useMutation({
    mutationFn: () => {
      return api.patch<ControlRecord>(`/controls/${controlId}`, {
        code: draft.code.trim(),
        name: draft.name.trim(),
        description: draft.description,
        status_code: draft.status_code,
        owner_user_id: draft.owner_user_id,
        implementation_notes: draft.implementation_notes,
        tags: draft.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
        revision: draft.revision,
      });
    },
    onSuccess: (control) => {
      const next = draftFrom(control);
      setBaseline(next);
      setDraft(next);
      setSaveState("saved");
      void queryClient.invalidateQueries({ queryKey: ["controls"] });
      void queryClient.invalidateQueries({ queryKey: ["requirements"] });
    },
    onError: (error) => setSaveState(error instanceof RevisionConflict ? "conflict" : "idle"),
  });
  const remove = useMutation({
    mutationFn: () => api.delete(`/requirements/${requirementId}/controls/${controlId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["requirements"] });
      void queryClient.invalidateQueries({ queryKey: ["requirement-related", requirementId, "controls"] });
      onRemoved?.();
    },
  });

  function changeTab(next: ControlTab): void {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    if (dirty) setDraft(baseline);
    setTab(next);
  }

  function goBack(): void {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    onBack();
  }

  return (
    <section className="control-detail">
      <header className="control-detail-heading">
        <button type="button" onClick={goBack}>← Back to mapped controls</button>
        <div><p className="eyebrow">Organizational control</p><h3>{draft.code} · {draft.name}</h3><span>Revision {draft.revision}</span></div>
        {canEdit && requirementId ? <button className="danger-button" disabled={remove.isPending} type="button" onClick={() => { if (window.confirm("Remove this control from the requirement?")) remove.mutate(); }}>Remove from requirement</button> : null}
      </header>
      {remove.isError ? <p className="form-error" role="alert">The control could not be removed from this requirement.</p> : null}
      <nav aria-label="Control sections" className="control-tabs" role="tablist">
        {(canEdit ? ["Overview", "Resources", "Assist", "Activity"] as ControlTab[] : ["Overview", "Resources", "Activity"] as ControlTab[]).map((item) => <button aria-selected={tab === item} key={item} onClick={() => changeTab(item)} role="tab" tabIndex={tab === item ? 0 : -1} type="button">{item}</button>)}
      </nav>
      {tab === "Overview" ? (
        <form className="control-detail-form" onSubmit={(event) => { event.preventDefault(); if (canEdit) save.mutate(); }}>
          <div className="sheet-field-row"><label>Control code<input disabled={!canEdit} maxLength={80} required value={draft.code} onChange={(event) => { setSaveState("idle"); setDraft({ ...draft, code: event.target.value }); }} /></label><label>Control name<input disabled={!canEdit} maxLength={240} required value={draft.name} onChange={(event) => { setSaveState("idle"); setDraft({ ...draft, name: event.target.value }); }} /></label></div>
          <label>Description<textarea disabled={!canEdit} maxLength={20000} rows={4} value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></label>
          <div className="sheet-field-row"><label>Operating status<select disabled={!canEdit} value={draft.status_code} onChange={(event) => setDraft({ ...draft, status_code: event.target.value as ControlRecord["status_code"] })}><option value="PLANNED">Planned</option><option value="IMPLEMENTING">Implementing</option><option value="OPERATING">Operating</option><option value="NEEDS_ATTENTION">Needs attention</option><option value="RETIRED">Retired</option></select></label><label>Owner<select disabled={!canEdit} value={draft.owner_user_id ?? ""} onChange={(event) => setDraft({ ...draft, owner_user_id: event.target.value || null })}><option value="">Unassigned</option>{directoryQuery.data?.map((person) => <option key={person.id} value={person.id}>{person.display_name}</option>)}</select></label></div>
          <label>Tags<input disabled={!canEdit} value={draft.tags} onChange={(event) => setDraft({ ...draft, tags: event.target.value })} /></label>
          <label>Implementation notes<textarea disabled={!canEdit} maxLength={100000} rows={8} value={draft.implementation_notes} onChange={(event) => setDraft({ ...draft, implementation_notes: event.target.value })} /></label>
          {saveState === "conflict" ? <div className="conflict-note" role="alert"><strong>Another editor changed this control.</strong><p>Your draft remains visible. Reload the current control before applying it again.</p></div> : null}
          {save.isError && saveState !== "conflict" ? <p className="form-error" role="alert">The control was not saved.</p> : null}
          {canEdit ? <footer className="control-savebar"><span aria-live="polite">{dirty ? "Unsaved" : saveState === "saved" ? "Saved" : "No pending changes"}</span><button disabled={!dirty} type="button" onClick={() => setDraft(baseline)}>Cancel edits</button><button className="primary-button" disabled={!dirty || save.isPending} type="submit">Save control changes</button></footer> : <p className="viewer-note">Viewer access · control fields are read only.</p>}
        </form>
      ) : tab === "Resources" ? <EntityResources canEdit={canEdit} entityId={controlId} entityType="control" initialDraft={resourceSuggestion} onDraftApplied={clearResourceSuggestion} /> : tab === "Assist" && canEdit ? <AssistPanel canEdit entityId={controlId} entityType="control" onImplementationDraft={(text) => { setSaveState("idle"); setDraft((current) => ({ ...current, implementation_notes: text })); setTab("Overview"); }} onResourceDraft={(nextDraft) => { setResourceSuggestion(nextDraft); setTab("Resources"); }} /> : activityQuery.isLoading ? <p className="resource-state">Loading control activity…</p> : activityQuery.isError ? <p className="form-error" role="alert">Control activity could not be loaded.</p> : (activityQuery.data ?? []).length ? <ul className="activity-list">{activityQuery.data?.map((event) => <li key={event.id}><strong>{formatActionCode(event.action_code)}</strong><span>{event.actor_display_name ?? "System"}</span>{event.change_summary ? <small>{event.change_summary}</small> : null}<time>{new Date(event.created_at).toLocaleString()}</time></li>)}</ul> : <p className="resource-state">No control activity recorded.</p>}
    </section>
  );
}
