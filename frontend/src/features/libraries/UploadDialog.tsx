import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { api } from "../../app/api/client";
import type { RequirementSummary } from "../../app/api/types";
import type { ControlOption, LibraryKind, LibraryRecord } from "./library-types";

const acceptedExtensions = ".pdf,.docx,.xlsx,.csv,.txt,.png,.jpg,.jpeg,.gif,.webp,.zip,.json";

export function UploadDialog({
  kind,
  open,
  onOpenChange,
  onUploaded,
  requirements,
  controls = [],
  initialRequirementIds = [],
  initialControlIds = [],
}: {
  kind: LibraryKind;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUploaded?: (record: LibraryRecord) => void;
  requirements: RequirementSummary[];
  controls?: ControlOption[];
  initialRequirementIds?: string[];
  initialControlIds?: string[];
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [date, setDate] = useState("");
  const [documentType, setDocumentType] = useState("POLICY");
  const [version, setVersion] = useState("");
  const [requirementIds, setRequirementIds] = useState<string[]>(initialRequirementIds);
  const [controlIds, setControlIds] = useState<string[]>(initialControlIds);
  const [requirementSearch, setRequirementSearch] = useState("");
  const [controlSearch, setControlSearch] = useState("");
  const visibleRequirements = useMemo(() => {
    const term = requirementSearch.trim().toLowerCase();
    return requirements.filter((item) => `${item.external_id} ${item.title}`.toLowerCase().includes(term));
  }, [requirementSearch, requirements]);
  const visibleControls = useMemo(() => {
    const term = controlSearch.trim().toLowerCase();
    return controls.filter((item) => `${item.code} ${item.name}`.toLowerCase().includes(term));
  }, [controlSearch, controls]);

  const mutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Choose a file.");
      const body = new FormData();
      body.set("file", file);
      body.set("name", name.trim());
      body.set("description", description);
      if (kind === "documents") {
        body.set("document_type", documentType);
        body.set("version", version);
        if (date) body.set("effective_date", date);
      } else if (date) body.set("evidence_date", date);
      for (const id of requirementIds) body.append("requirement_ids", id);
      for (const id of controlIds) body.append("control_ids", id);
      return api.upload<LibraryRecord>(`/${kind}`, body);
    },
    onSuccess: (record) => {
      onUploaded?.(record);
      void queryClient.invalidateQueries({ queryKey: ["library", kind] });
      void queryClient.invalidateQueries({ queryKey: ["requirements"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      onOpenChange(false);
    },
  });

  function toggle(id: string, selected: string[], setSelected: (ids: string[]) => void): void {
    setSelected(selected.includes(id) ? selected.filter((candidate) => candidate !== id) : [...selected, id]);
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <div aria-hidden="true" className="dialog-scrim" />
        <Dialog.Content className="upload-dialog">
          <header><div><p className="eyebrow">Secure file upload</p><Dialog.Title>Upload {kind === "documents" ? "document" : "evidence"}</Dialog.Title><Dialog.Description>Store one validated file and optionally attach it to requirements or organizational controls.</Dialog.Description></div><Dialog.Close aria-label="Close upload">×</Dialog.Close></header>
          <form noValidate onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
            <div className="upload-fields">
              <label>Name<input required value={name} onChange={(event) => setName(event.target.value)} /></label>
              <label>File<input accept={acceptedExtensions} required type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
              <p className="upload-help">PDF, DOCX, XLSX, CSV, TXT, images, ZIP, and JSON are accepted. Files are downloaded as attachments and never executed or previewed inline.</p>
              <label>Description<textarea rows={3} value={description} onChange={(event) => setDescription(event.target.value)} /></label>
              {kind === "documents" ? <>
                <label>Document type<select value={documentType} onChange={(event) => setDocumentType(event.target.value)}><option value="POLICY">Policy</option><option value="STANDARD">Standard</option><option value="PROCEDURE">Procedure</option><option value="PLAN">Plan</option><option value="GUIDELINE">Guideline</option><option value="OTHER">Other</option></select></label>
                <label>Version<input value={version} onChange={(event) => setVersion(event.target.value)} /></label>
              </> : null}
              <label>{kind === "documents" ? "Effective date" : "Evidence date"}<input type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
            </div>
            {requirementIds.length + controlIds.length > 0 ? <p className="target-summary" role="status">This upload will be attached to {requirementIds.length + controlIds.length} selected targets.</p> : null}
            <fieldset className="mapping-picker"><legend>Map to requirements <span>{requirementIds.length} selected</span></legend><label className="mapping-search">Search requirements<input type="search" value={requirementSearch} onChange={(event) => setRequirementSearch(event.target.value)} /></label><div>{visibleRequirements.map((requirement) => <label key={requirement.id}><input type="checkbox" checked={requirementIds.includes(requirement.id)} onChange={() => toggle(requirement.id, requirementIds, setRequirementIds)} /> <strong>{requirement.external_id}</strong> {requirement.title}</label>)}</div></fieldset>
            {controls.length ? <fieldset className="mapping-picker"><legend>Map to controls <span>{controlIds.length} selected</span></legend><label className="mapping-search">Search controls<input type="search" value={controlSearch} onChange={(event) => setControlSearch(event.target.value)} /></label><div>{visibleControls.map((control) => <label key={control.id}><input type="checkbox" checked={controlIds.includes(control.id)} onChange={() => toggle(control.id, controlIds, setControlIds)} /> <strong>{control.code}</strong> {control.name}</label>)}</div></fieldset> : null}
            {mutation.isError ? <p className="form-error" role="alert">{mutation.error instanceof Error ? mutation.error.message : "Upload failed."}</p> : null}
            <footer><Dialog.Close type="button">Cancel</Dialog.Close><button className="primary-button" disabled={!name.trim() || !file || mutation.isPending} type="submit">{mutation.isPending ? "Uploading…" : "Upload"}</button></footer>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
