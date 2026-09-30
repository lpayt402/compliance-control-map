import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { api } from "../../app/api/client";
import type {
  PersonSummary,
  RequirementSummary,
  TextResource,
  TextResourceKind,
} from "../../app/api/types";
import { formatDateOnly } from "../../design/format";
import type {
  ControlOption,
  LibraryKind,
  LibraryRecord,
} from "../libraries/library-types";
import { UploadDialog } from "../libraries/UploadDialog";
import type { AssistanceResourceDraft } from "./AssistPanel";

type EntityType = "requirement" | "control";

function bytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function entityPath(type: EntityType, id: string): string {
  return `/${type === "requirement" ? "requirements" : "controls"}/${id}`;
}

function FileSection({
  canEdit,
  entityId,
  entityType,
  kind,
  onUpload,
}: {
  canEdit: boolean;
  entityId: string;
  entityType: EntityType;
  kind: LibraryKind;
  onUpload: () => void;
}) {
  const queryClient = useQueryClient();
  const noun = kind === "documents" ? "document" : "evidence";
  const linkedQuery = useQuery({
    queryKey: ["entity-resources", entityType, entityId, kind],
    queryFn: () => api.get<LibraryRecord[]>(`${entityPath(entityType, entityId)}/${kind}`),
  });
  const libraryQuery = useQuery({
    queryKey: ["library", kind],
    queryFn: () => api.get<LibraryRecord[]>(`/${kind}`),
    enabled: canEdit,
  });
  const [selectedId, setSelectedId] = useState("");
  const [search, setSearch] = useState("");
  const linkedIds = new Set((linkedQuery.data ?? []).map((item) => item.id));
  const available = (libraryQuery.data ?? []).filter((item) => !linkedIds.has(item.id));
  const visibleAvailable = available.filter((item) => `${item.name} ${item.file.original_filename}`.toLowerCase().includes(search.trim().toLowerCase()));
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      queryKey: ["entity-resources", entityType, entityId, kind],
    });
    void queryClient.invalidateQueries({ queryKey: ["library", kind] });
    void queryClient.invalidateQueries({ queryKey: ["requirements"] });
  };
  const link = useMutation({
    mutationFn: () => api.post(`${entityPath(entityType, entityId)}/${kind}`, {
      [kind === "documents" ? "document_ids" : "evidence_ids"]: [selectedId],
      ...(entityType === "requirement" ? { rationale: "" } : {}),
    }),
    onSuccess: () => { setSelectedId(""); refresh(); },
  });
  const detach = useMutation({
    mutationFn: (recordId: string) => api.delete(
      `${entityPath(entityType, entityId)}/${kind}/${recordId}`,
    ),
    onSuccess: refresh,
  });

  return (
    <section className="resource-category">
      <header>
        <div><p className="eyebrow">File resources</p><h3>{kind === "documents" ? "Documents" : "Evidence"}</h3></div>
        {canEdit ? <button type="button" onClick={onUpload}>Upload new {noun}</button> : null}
      </header>
      {canEdit && available.length ? (
        <form className="resource-linker" onSubmit={(event) => { event.preventDefault(); link.mutate(); }}>
          <label>
            Search existing {kind}
            <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} />
          </label>
          <label>
            Link existing {noun}
            <select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
              <option value="">Choose {noun}</option>
              {visibleAvailable.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <button disabled={!selectedId || link.isPending} type="submit">Link {noun}</button>
        </form>
      ) : null}
      {linkedQuery.isLoading ? <p className="resource-state">Loading {noun} records…</p>
        : linkedQuery.isError ? <p className="form-error" role="alert">{noun === "document" ? "Documents" : "Evidence"} could not be loaded.</p>
          : (linkedQuery.data ?? []).length ? (
            <ul className="resource-files">
              {linkedQuery.data?.map((item) => (
                <li key={item.id}>
                  <div><strong>{item.name}</strong><span>{item.file.original_filename}</span>{item.description ? <p>{item.description}</p> : null}</div>
                  <dl><div><dt>Class</dt><dd>{item.document_type ?? "Evidence"}</dd></div><div><dt>Safe type</dt><dd>{item.file.detected_media_type}</dd></div><div><dt>Size</dt><dd>{bytes(item.file.byte_size)}</dd></div><div><dt>Date</dt><dd>{item.effective_date || item.evidence_date ? formatDateOnly(item.effective_date ?? item.evidence_date) : new Date(item.updated_at).toLocaleDateString()}</dd></div><div><dt>Owner</dt><dd>{item.owner?.display_name ?? (item.owner_user_id ? "Assigned" : "Unassigned")}</dd></div></dl>
                  <div className="resource-actions"><a download href={`/api/v1/${kind}/${item.id}/download`}>Download</a>{canEdit ? <button type="button" onClick={() => { if (window.confirm(`Detach ${noun}?`)) detach.mutate(item.id); }}>Detach</button> : null}</div>
                </li>
              ))}
            </ul>
          ) : <p className="resource-state">No {kind === "documents" ? "documents" : "evidence"} attached.</p>}
      {link.isError ? <p className="form-error" role="alert">The {noun} could not be linked.</p> : null}
      {detach.isError ? <p className="form-error" role="alert">The {noun} could not be detached.</p> : null}
    </section>
  );
}

export function EntityResources({
  canEdit,
  entityId,
  entityType,
  initialDraft = null,
  onDraftApplied,
}: {
  canEdit: boolean;
  entityId: string;
  entityType: EntityType;
  initialDraft?: AssistanceResourceDraft | null;
  onDraftApplied?: () => void;
}) {
  const queryClient = useQueryClient();
  const [uploadKind, setUploadKind] = useState<LibraryKind | null>(null);
  const [editing, setEditing] = useState<TextResource | null>(null);
  const [formOpen, setFormOpen] = useState(Boolean(initialDraft));
  const [kind, setKind] = useState<TextResourceKind>(initialDraft?.kind ?? "NOTE");
  const [title, setTitle] = useState(initialDraft?.title ?? "");
  const [body, setBody] = useState(initialDraft?.body ?? "");
  const [contactUserId, setContactUserId] = useState("");
  const path = entityPath(entityType, entityId);
  const resourcesQuery = useQuery({
    queryKey: ["entity-resources", entityType, entityId, "notes"],
    queryFn: () => api.get<TextResource[]>(`${path}/notes`),
  });
  const directoryQuery = useQuery({
    queryKey: ["user-directory"],
    queryFn: () => api.get<Array<Pick<PersonSummary, "id" | "display_name">>>("/users/directory"),
  });
  const requirementsQuery = useQuery({
    queryKey: ["requirements", "resource-upload"],
    queryFn: () => api.get<RequirementSummary[]>("/requirements?limit=200"),
    enabled: canEdit,
  });
  const controlsQuery = useQuery({
    queryKey: ["controls"],
    queryFn: () => api.get<ControlOption[]>("/controls"),
    enabled: canEdit,
  });
  const refreshResources = (): void => {
    void queryClient.invalidateQueries({
      queryKey: ["entity-resources", entityType, entityId, "notes"],
    });
  };
  const saveResource = useMutation({
    mutationFn: () => editing
      ? api.patch<TextResource>(`${path}/notes/${editing.id}`, {
          revision: editing.revision,
          kind,
          title,
          body,
          contact_user_id: kind === "CONTACT" && contactUserId ? contactUserId : null,
        })
      : api.post<TextResource>(`${path}/notes`, {
          kind,
          title,
          body,
          contact_user_id: kind === "CONTACT" && contactUserId ? contactUserId : null,
        }),
    onSuccess: () => { closeForm(); refreshResources(); },
  });
  const removeResource = useMutation({
    mutationFn: (resource: TextResource) => api.delete(
      `${path}/notes/${resource.id}?revision=${resource.revision}`,
    ),
    onSuccess: refreshResources,
  });
  const grouped = useMemo(() => ({
    NOTE: (resourcesQuery.data ?? []).filter((item) => item.kind === "NOTE"),
    PLAYBOOK: (resourcesQuery.data ?? []).filter((item) => item.kind === "PLAYBOOK"),
    CONTACT: (resourcesQuery.data ?? []).filter((item) => item.kind === "CONTACT"),
  }), [resourcesQuery.data]);

  function closeForm(): void {
    setFormOpen(false);
    setEditing(null);
    setKind("NOTE");
    setTitle("");
    setBody("");
    setContactUserId("");
    onDraftApplied?.();
  }

  function editResource(resource: TextResource): void {
    setEditing(resource);
    setKind(resource.kind);
    setTitle(resource.title);
    setBody(resource.body);
    setContactUserId(resource.contact_user_id ?? "");
    setFormOpen(true);
  }

  return (
    <div className="entity-resources">
      <FileSection canEdit={canEdit} entityId={entityId} entityType={entityType} kind="documents" onUpload={() => setUploadKind("documents")} />
      <FileSection canEdit={canEdit} entityId={entityId} entityType={entityType} kind="evidence" onUpload={() => setUploadKind("evidence")} />
      <section className="resource-category text-resources">
        <header><div><p className="eyebrow">Plain-text resources</p><h3>Notes, playbooks, and contacts</h3></div>{canEdit ? <button type="button" onClick={() => setFormOpen(true)}>Add text resource</button> : null}</header>
        {formOpen ? (
          <form className="text-resource-form" onSubmit={(event) => { event.preventDefault(); saveResource.mutate(); }}>
            <label>Resource type<select value={kind} onChange={(event) => setKind(event.target.value as TextResourceKind)}><option value="NOTE">Note</option><option value="PLAYBOOK">Playbook</option><option value="CONTACT">Contact</option></select></label>
            <label>Title<input required={kind !== "NOTE"} maxLength={240} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
            {kind === "CONTACT" ? <label>Workspace contact<select value={contactUserId} onChange={(event) => setContactUserId(event.target.value)}><option value="">Free-form contact</option>{directoryQuery.data?.map((person) => <option key={person.id} value={person.id}>{person.display_name}</option>)}</select></label> : null}
            <label className="resource-body">Text<textarea required maxLength={10000} rows={6} value={body} onChange={(event) => setBody(event.target.value)} /></label>
            {saveResource.isError ? <p className="form-error" role="alert">The resource was not saved. Reload if another editor changed it.</p> : null}
            <footer><button type="button" onClick={closeForm}>Cancel</button><button className="primary-button" disabled={!body.trim() || (kind !== "NOTE" && !title.trim()) || saveResource.isPending} type="submit">Save resource</button></footer>
          </form>
        ) : null}
        {resourcesQuery.isLoading ? <p className="resource-state">Loading text resources…</p> : resourcesQuery.isError ? <p className="form-error" role="alert">Text resources could not be loaded.</p> : (
          <div className="text-resource-groups">
            {(["NOTE", "PLAYBOOK", "CONTACT"] as TextResourceKind[]).map((resourceKind) => (
              <section key={resourceKind}>
                <h4>{resourceKind === "NOTE" ? "Notes" : resourceKind === "PLAYBOOK" ? "Playbooks" : "Contacts"} <span>{grouped[resourceKind].length}</span></h4>
                {grouped[resourceKind].length ? <ul>{grouped[resourceKind].map((resource) => <li key={resource.id}><header><div><strong>{resource.title || "Untitled note"}</strong><small>Revision {resource.revision} · {new Date(resource.edited_at ?? resource.created_at).toLocaleDateString()}</small></div>{canEdit ? <div className="resource-actions"><button type="button" onClick={() => editResource(resource)}>Edit</button><button type="button" onClick={() => { if (window.confirm("Delete this text resource?")) removeResource.mutate(resource); }}>Delete</button></div> : null}</header><p>{resource.body}</p>{resource.contact_user ? <small>Workspace contact: {resource.contact_user.display_name}</small> : null}</li>)}</ul> : <p>No {resourceKind.toLowerCase()} resources.</p>}
              </section>
            ))}
          </div>
        )}
        {removeResource.isError ? <p className="form-error" role="alert">The text resource could not be deleted.</p> : null}
      </section>
      {uploadKind ? <UploadDialog controls={controlsQuery.data ?? []} initialControlIds={entityType === "control" ? [entityId] : []} initialRequirementIds={entityType === "requirement" ? [entityId] : []} kind={uploadKind} onOpenChange={(open) => { if (!open) setUploadKind(null); }} onUploaded={() => { void queryClient.invalidateQueries({ queryKey: ["entity-resources"] }); }} open requirements={requirementsQuery.data ?? []} /> : null}
    </div>
  );
}
