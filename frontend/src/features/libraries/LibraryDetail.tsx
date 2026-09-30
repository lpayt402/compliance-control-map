import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../../app/api/client";
import type { RequirementSummary } from "../../app/api/types";
import type { ControlOption, LibraryKind, LibraryRecord } from "./library-types";

function bytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function LibraryDetail({ record, kind, requirements, controls, canEdit }: { record: LibraryRecord; kind: LibraryKind; requirements: RequirementSummary[]; controls: ControlOption[]; canEdit: boolean }) {
  const queryClient = useQueryClient();
  const [mapping, setMapping] = useState<string[]>([]);
  const [controlMapping, setControlMapping] = useState("");
  const available = requirements.filter((item) => !record.requirements.some((linked) => linked.id === item.id));
  const availableControls = controls.filter((item) => !record.controls.some((linked) => linked.id === item.id));
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: ["library", kind] });
    void queryClient.invalidateQueries({ queryKey: ["requirements"] });
    void queryClient.invalidateQueries({ queryKey: ["controls"] });
  };
  const requirementMutation = useMutation({
    mutationFn: () => api.post<LibraryRecord>(`/${kind}/${record.id}/requirements`, { requirement_ids: mapping, rationale: "" }),
    onSuccess: () => { setMapping([]); refresh(); },
  });
  const controlMutation = useMutation({
    mutationFn: () => api.post<LibraryRecord>(`/${kind}/${record.id}/controls`, { control_ids: [controlMapping] }),
    onSuccess: () => { setControlMapping(""); refresh(); },
  });
  const detachMutation = useMutation({
    mutationFn: ({ targetType, targetId }: { targetType: "requirements" | "controls"; targetId: string }) => api.delete(`/${targetType}/${targetId}/${kind}/${record.id}`),
    onSuccess: refresh,
  });

  return (
    <aside className="library-detail" aria-label={`${record.name} details`}>
      <header><p className="eyebrow">{kind === "documents" ? record.document_type?.toLowerCase() : "Evidence artifact"}</p><h2>{record.name}</h2><p>{record.description || "No description."}</p></header>
      <dl className="file-ledger"><div><dt>File</dt><dd>{record.file.original_filename}</dd></div><div><dt>Size</dt><dd>{bytes(record.file.byte_size)}</dd></div><div><dt>Type</dt><dd>{record.file.detected_media_type}</dd></div><div><dt>Updated</dt><dd>{new Date(record.updated_at).toLocaleDateString()}</dd></div></dl>
      <a className="download-link" href={`/api/v1/${kind}/${record.id}/download`} download>Download attachment</a>
      <section className="relationship-ledger"><h3>Requirement coverage <span>{record.requirements.length}</span></h3>{record.requirements.length ? <ul>{record.requirements.map((item) => <li key={item.mapping_id}><strong>{item.external_id}</strong><span>{item.title}</span><small>{item.framework.toUpperCase()}</small>{canEdit ? <button aria-label={`Detach ${item.external_id}`} type="button" onClick={() => { if (window.confirm(`Detach ${item.external_id}?`)) detachMutation.mutate({ targetType: "requirements", targetId: item.id }); }}>Detach</button> : null}</li>)}</ul> : <p>No direct requirement mappings.</p>}</section>
      <section className="relationship-ledger"><h3>Control coverage <span>{record.controls.length}</span></h3>{record.controls.length ? <ul>{record.controls.map((item) => <li key={item.id}><strong>{item.code}</strong><span>{item.name}</span>{canEdit ? <button aria-label={`Detach ${item.code}`} type="button" onClick={() => { if (window.confirm(`Detach ${item.code}?`)) detachMutation.mutate({ targetType: "controls", targetId: item.id }); }}>Detach</button> : null}</li>)}</ul> : <p>No organizational control mappings.</p>}</section>
      {canEdit && available.length ? <form className="add-mappings" onSubmit={(event) => { event.preventDefault(); requirementMutation.mutate(); }}><fieldset><legend>Add requirement mappings</legend>{available.map((item) => <label key={item.id}><input type="checkbox" checked={mapping.includes(item.id)} onChange={() => setMapping((current) => current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id])} /> {item.external_id} · {item.title}</label>)}</fieldset><button disabled={!mapping.length || requirementMutation.isPending} type="submit">Map selected requirements</button></form> : null}
      {canEdit && availableControls.length ? <form className="add-mappings add-control-mapping" onSubmit={(event) => { event.preventDefault(); controlMutation.mutate(); }}><label>Add control mapping<select value={controlMapping} onChange={(event) => setControlMapping(event.target.value)}><option value="">Choose a control</option>{availableControls.map((control) => <option key={control.id} value={control.id}>{control.code} · {control.name}</option>)}</select></label><button disabled={!controlMapping || controlMutation.isPending} type="submit">Map selected controls</button></form> : null}
      {requirementMutation.isError || controlMutation.isError ? <p className="form-error" role="alert">The selected mapping could not be added.</p> : null}
      {detachMutation.isError ? <p className="form-error" role="alert">The selected mapping could not be detached.</p> : null}
    </aside>
  );
}
