import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../../app/api/client";
import { ControlDetail } from "./ControlDetail";

interface ControlRecord {
  id: string;
  code: string;
  name: string;
  description: string;
  status_code: string;
}

interface ControlMapping {
  id: string;
  coverage: string;
  rationale: string;
  control: ControlRecord;
}

export function ControlPanel({ requirementId, canEdit }: { requirementId: string; canEdit: boolean }) {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [existingId, setExistingId] = useState("");
  const [selectedControlId, setSelectedControlId] = useState<string | null>(null);
  const mappingsQuery = useQuery({
    queryKey: ["requirement-related", requirementId, "controls"],
    queryFn: () => api.get<ControlMapping[]>(`/requirements/${requirementId}/controls`),
  });
  const controlsQuery = useQuery({
    queryKey: ["controls"],
    queryFn: () => api.get<ControlRecord[]>("/controls"),
    enabled: canEdit,
  });
  const mappedIds = new Set((mappingsQuery.data ?? []).map((mapping) => mapping.control.id));
  const available = (controlsQuery.data ?? []).filter((control) => !mappedIds.has(control.id));

  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: ["requirement-related", requirementId, "controls"] });
    void queryClient.invalidateQueries({ queryKey: ["requirements"] });
    void queryClient.invalidateQueries({ queryKey: ["controls"] });
  };
  const createMutation = useMutation({
    mutationFn: async () => {
      const control = await api.post<ControlRecord>("/controls", {
        code: code.trim(),
        name: name.trim(),
        description,
        status_code: "PLANNED",
        implementation_notes: "",
        tags: [],
      });
      await api.post(`/requirements/${requirementId}/controls`, {
        control_id: control.id,
        coverage: "PRIMARY",
        rationale: "",
      });
      return control;
    },
    onSuccess: () => {
      setCreating(false);
      setCode("");
      setName("");
      setDescription("");
      refresh();
    },
  });
  const linkMutation = useMutation({
    mutationFn: () => api.post(`/requirements/${requirementId}/controls`, {
      control_id: existingId,
      coverage: "SUPPORTING",
      rationale: "",
    }),
    onSuccess: () => { setExistingId(""); refresh(); },
  });

  if (selectedControlId) {
    return (
      <ControlDetail
        canEdit={canEdit}
        controlId={selectedControlId}
        onBack={() => setSelectedControlId(null)}
        onRemoved={() => { setSelectedControlId(null); refresh(); }}
        requirementId={requirementId}
      />
    );
  }

  return (
    <section className="control-panel">
      <header><div><p className="eyebrow">Organizational layer</p><h3>Controls that do the work</h3></div>{canEdit ? <button onClick={() => setCreating((current) => !current)} type="button">{creating ? "Cancel control" : "Create control"}</button> : null}</header>
      <p className="concept-note">Requirement readiness, control operation, and evidence coverage remain separate. Mapping a control does not transfer a status.</p>
      {creating ? <form className="control-form" onSubmit={(event) => { event.preventDefault(); createMutation.mutate(); }}>
        <label>Control code<input required value={code} onChange={(event) => setCode(event.target.value)} placeholder="AC-01" /></label>
        <label>Control name<input required value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label className="control-description">Description<textarea rows={3} value={description} onChange={(event) => setDescription(event.target.value)} /></label>
        {createMutation.isError ? <p className="form-error" role="alert">The control could not be created.</p> : null}
        <button className="primary-button" disabled={!code.trim() || !name.trim() || createMutation.isPending} type="submit">{createMutation.isPending ? "Saving…" : "Save control"}</button>
      </form> : null}
      {canEdit && available.length ? <form className="link-control" onSubmit={(event) => { event.preventDefault(); linkMutation.mutate(); }}><label>Map an existing control<select value={existingId} onChange={(event) => setExistingId(event.target.value)}><option value="">Choose a control</option>{available.map((control) => <option key={control.id} value={control.id}>{control.code} · {control.name}</option>)}</select></label><button disabled={!existingId || linkMutation.isPending} type="submit">Map control</button></form> : null}
      {linkMutation.isError ? <p className="form-error" role="alert">The control could not be mapped.</p> : null}
      {mappingsQuery.isLoading ? <p className="sheet-empty">Loading control coverage…</p> : mappingsQuery.isError ? <p className="sheet-empty sheet-empty--error">Controls could not be loaded.</p> : (mappingsQuery.data ?? []).length ? <ul className="control-mappings">{mappingsQuery.data?.map((mapping) => <li key={mapping.id}><button type="button" onClick={() => setSelectedControlId(mapping.control.id)}><strong>{mapping.control.code}</strong><span>{mapping.control.name}</span><small>{mapping.coverage} · {mapping.control.status_code}</small><b>Open control</b></button></li>)}</ul> : <p className="sheet-empty">No organizational controls mapped.</p>}
    </section>
  );
}
