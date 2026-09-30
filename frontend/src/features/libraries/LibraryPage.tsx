import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { api } from "../../app/api/client";
import type { RequirementSummary } from "../../app/api/types";
import { useSession } from "../../app/session/session-context";
import { LibraryDetail } from "./LibraryDetail";
import type { ControlOption, LibraryKind, LibraryRecord } from "./library-types";
import { UploadDialog } from "./UploadDialog";

export function LibraryPage({ kind }: { kind: LibraryKind }) {
  const { user } = useSession();
  const canEdit = user?.role !== "VIEWER";
  const [uploadOpen, setUploadOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const recordsQuery = useQuery({ queryKey: ["library", kind], queryFn: () => api.get<LibraryRecord[]>(`/${kind}`) });
  const requirementsQuery = useQuery({ queryKey: ["requirements", "library"], queryFn: () => api.get<RequirementSummary[]>("/requirements?limit=200") });
  const controlsQuery = useQuery({ queryKey: ["controls"], queryFn: () => api.get<ControlOption[]>("/controls") });
  const records = useMemo(() => recordsQuery.data ?? [], [recordsQuery.data]);
  const filtered = useMemo(() => records.filter((record) => `${record.name} ${record.description} ${record.file.original_filename}`.toLowerCase().includes(search.trim().toLowerCase())), [records, search]);
  const selected = records.find((record) => record.id === selectedId) ?? filtered[0] ?? null;
  const noun = kind === "documents" ? "Documents" : "Evidence";

  return (
    <section className="library-page">
      <header className="operational-heading"><div><p className="eyebrow">{kind === "documents" ? "Controlled documents" : "Evidence records"}</p><h1>{noun}</h1></div><p>Upload validated files, manage requirement and control links, and download attachments safely.</p></header>
      <div className="library-toolbar"><label>Search {noun.toLowerCase()}<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} /></label><span role="status">{filtered.length} file{filtered.length === 1 ? "" : "s"}</span>{canEdit ? <button className="primary-button" onClick={() => setUploadOpen(true)}>Upload {kind === "documents" ? "document" : "evidence"}</button> : null}</div>
      {recordsQuery.isLoading ? <p className="operational-state">Loading {noun.toLowerCase()}…</p> : recordsQuery.isError ? <p className="operational-state">The {noun.toLowerCase()} library could not be loaded.</p> : filtered.length === 0 ? <div className="library-empty"><strong>No files have been added.</strong><p>{canEdit ? `Upload the first ${kind === "documents" ? "document" : "evidence file"}.` : "An editor can add files to this library."}</p></div> : <div className="library-workspace"><div className="library-index" role="list">{filtered.map((record) => <button className={selected?.id === record.id ? "is-selected" : ""} key={record.id} onClick={() => setSelectedId(record.id)} role="listitem"><strong>{record.name}</strong><span>{record.file.original_filename}</span><small>{record.requirements.length} requirements · {record.controls.length} controls</small></button>)}</div>{selected ? <LibraryDetail canEdit={canEdit} controls={controlsQuery.data ?? []} kind={kind} record={selected} requirements={requirementsQuery.data ?? []} /> : null}</div>}
      {uploadOpen ? <UploadDialog kind={kind} open onOpenChange={setUploadOpen} onUploaded={(record) => setSelectedId(record.id)} requirements={requirementsQuery.data ?? []} controls={controlsQuery.data ?? []} /> : null}
    </section>
  );
}
