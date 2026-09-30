import { useMutation } from "@tanstack/react-query";

import { api } from "../../app/api/client";

export function ExportPanel() {
  const mutation = useMutation({
    mutationFn: () => api.download("/exports", "POST"),
    onSuccess: ({ blob, filename }) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    },
  });
  return (
    <section className="settings-section">
      <div><p className="eyebrow">Portability</p><h2>Backup and export</h2><p>Create one structured ZIP with workspace data, mappings, metadata, and stored files. Password hashes and active sessions are excluded.</p></div>
      <button className="primary-button" disabled={mutation.isPending} onClick={() => mutation.mutate()}>{mutation.isPending ? "Preparing…" : "Create backup"}</button>
      {mutation.isError ? <p className="form-error" role="alert">Backup could not be created.</p> : null}
    </section>
  );
}
