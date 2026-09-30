import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError, api } from "../../app/api/client";
import type { InferenceProvider, InferenceStatus } from "../../app/api/types";

interface ProviderTestResult {
  reachable: boolean;
  model_accepted: boolean;
  latency_ms: number | null;
  error_code: string | null;
  message: string;
}

const EMPTY_FORM = {
  provider_identifier: "",
  display_name: "",
  base_url: "",
  model_id: "",
  secret_ref: "",
  timeout_seconds: 60,
  tls_policy: "REQUIRED" as InferenceProvider["tls_policy"],
  data_policy: "LOCAL_ONLY" as InferenceProvider["data_policy"],
  streaming: true,
  tool_calls: false,
  structured_output: false,
  enabled: false,
  is_default: false,
};

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.detail : "The request could not be completed.";
}

function secretLabel(status: InferenceProvider["secret_status"]): string {
  if (status === "NOT_REQUIRED") return "Not required";
  if (status === "CONFIGURED") return "Configured by environment reference";
  return "Environment reference is missing";
}

export function ProviderPanel() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [testResults, setTestResults] = useState<Record<string, ProviderTestResult>>({});
  const statusQuery = useQuery({
    queryKey: ["inference", "status"],
    queryFn: () => api.get<InferenceStatus>("/inference/status"),
  });
  const providersQuery = useQuery({
    queryKey: ["inference", "providers"],
    queryFn: () => api.get<InferenceProvider[]>("/inference/providers"),
  });
  const providers = Array.isArray(providersQuery.data) ? providersQuery.data : [];

  const createProvider = useMutation({
    mutationFn: () => api.post<InferenceProvider>("/inference/providers", {
      provider_identifier: form.provider_identifier.trim(),
      display_name: form.display_name.trim(),
      base_url: form.base_url.trim(),
      model_id: form.model_id.trim(),
      api_mode: "CHAT_COMPLETIONS",
      capabilities: {
        streaming: form.streaming,
        tool_calls: form.tool_calls,
        structured_output: form.structured_output,
        embeddings: false,
        max_context_tokens: null,
      },
      timeout_seconds: form.timeout_seconds,
      tls_policy: form.tls_policy,
      data_policy: form.data_policy,
      secret_ref: form.secret_ref.trim() || null,
      enabled: form.enabled,
      is_default: form.is_default,
    }),
    onSuccess: (provider) => {
      queryClient.setQueryData<InferenceProvider[]>(["inference", "providers"], (current) => [
        ...(Array.isArray(current) ? current : []),
        provider,
      ]);
      setForm(EMPTY_FORM);
      setFormOpen(false);
    },
  });

  const testProvider = useMutation({
    mutationFn: (provider: InferenceProvider) => api.post<ProviderTestResult>(
      `/inference/providers/${provider.id}/test`,
      {},
    ),
    onSuccess: (result, provider) => setTestResults((current) => ({
      ...current,
      [provider.id]: result,
    })),
  });
  const updateProvider = useMutation({
    mutationFn: ({ provider, changes }: { provider: InferenceProvider; changes: Record<string, unknown> }) => api.patch<InferenceProvider>(`/inference/providers/${provider.id}`, { revision: provider.revision, ...changes }),
    onSuccess: (updated) => queryClient.setQueryData<InferenceProvider[]>(["inference", "providers"], (current) => (Array.isArray(current) ? current.map((item) => item.id === updated.id ? updated : item.is_default && updated.is_default ? { ...item, is_default: false } : item) : [updated])),
  });
  const deleteProvider = useMutation({
    mutationFn: (provider: InferenceProvider) => api.delete(`/inference/providers/${provider.id}`),
    onSuccess: (_data, provider) => queryClient.setQueryData<InferenceProvider[]>(["inference", "providers"], (current) => (Array.isArray(current) ? current.filter((item) => item.id !== provider.id) : [])),
  });

  const status = statusQuery.data;
  const readinessLabel = !status?.enabled
    ? "Disabled by server"
    : status.ready
      ? "Enabled and ready"
      : "Configuration error";

  return (
    <section className="settings-section provider-settings">
      <div>
        <p className="eyebrow">Optional, advisory assistance</p>
        <h2>Model providers</h2>
        <p>Administrators can register allowlisted OpenAI-compatible endpoints. Credentials remain in environment variables; this workspace stores only an <code>env:NAME</code> reference.</p>
        <p className="provider-readiness" aria-live="polite">{readinessLabel}</p>
        {status?.allowed_base_urls.length ? (
          <details><summary>Allowed destinations</summary><ul>{status.allowed_base_urls.map((url) => <li key={url}><code>{url}</code></li>)}</ul></details>
        ) : null}
      </div>
      <div className="provider-console">
        <button type="button" onClick={() => setFormOpen((current) => !current)}>{formOpen ? "Cancel provider" : "Add provider"}</button>
        {formOpen ? (
          <form className="provider-form" onSubmit={(event) => { event.preventDefault(); createProvider.mutate(); }}>
            <label>Profile ID<input required value={form.provider_identifier} onChange={(event) => setForm({ ...form, provider_identifier: event.target.value })} /></label>
            <label>Display name<input required value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} /></label>
            <label className="provider-wide">Base URL<input required type="url" value={form.base_url} onChange={(event) => setForm({ ...form, base_url: event.target.value })} /></label>
            <label>Model ID<input required value={form.model_id} onChange={(event) => setForm({ ...form, model_id: event.target.value })} /></label>
            <label>Secret reference<input placeholder="env:MODEL_API_KEY" value={form.secret_ref} onChange={(event) => setForm({ ...form, secret_ref: event.target.value })} /><small>Reference only. Never enter a credential.</small></label>
            <label>TLS policy<select value={form.tls_policy} onChange={(event) => setForm({ ...form, tls_policy: event.target.value as InferenceProvider["tls_policy"] })}><option value="REQUIRED">TLS required</option><option value="PRIVATE_CA_ALLOWED">Private CA allowed</option><option value="PLAINTEXT_LOCAL_ONLY">Plaintext local only</option></select></label>
            <label>Data policy<select value={form.data_policy} onChange={(event) => setForm({ ...form, data_policy: event.target.value as InferenceProvider["data_policy"] })}><option value="LOCAL_ONLY">Local only</option><option value="REDACTED_EXTERNAL">Redacted external</option><option value="EXTERNAL_ALLOWED">External allowed</option></select></label>
            <fieldset className="provider-capabilities provider-wide"><legend>Declared capabilities</legend><label><input checked={form.streaming} type="checkbox" onChange={(event) => setForm({ ...form, streaming: event.target.checked })} /> Streaming</label><label><input checked={form.tool_calls} type="checkbox" onChange={(event) => setForm({ ...form, tool_calls: event.target.checked })} /> Tool calls</label><label><input checked={form.structured_output} type="checkbox" onChange={(event) => setForm({ ...form, structured_output: event.target.checked })} /> Structured output</label></fieldset>
            <label className="provider-enable provider-wide"><input checked={form.enabled} disabled={!status?.enabled} type="checkbox" onChange={(event) => setForm({ ...form, enabled: event.target.checked, is_default: event.target.checked ? form.is_default : false })} /> Enable this profile after saving</label>
            <label className="provider-enable provider-wide"><input checked={form.is_default} disabled={!form.enabled} type="checkbox" onChange={(event) => setForm({ ...form, is_default: event.target.checked })} /> Make this the default profile</label>
            <button className="primary-button provider-wide" disabled={createProvider.isPending} type="submit">{createProvider.isPending ? "Saving…" : "Save provider"}</button>
            {createProvider.isError ? <p className="form-error provider-wide" role="alert">{errorMessage(createProvider.error)}</p> : null}
          </form>
        ) : null}
        <ul className="provider-list">
          {providers.map((provider) => {
            const result = testResults[provider.id];
            return (
              <li key={provider.id}>
                <div><strong>{provider.display_name}{provider.is_default ? " · Default" : ""}</strong><code>{provider.model_id}</code><small>{provider.base_url}</small></div>
                <dl><div><dt>Status</dt><dd>{provider.enabled ? "Enabled" : "Disabled"}</dd></div><div><dt>Secret</dt><dd>{secretLabel(provider.secret_status)}</dd></div><div><dt>Data / TLS</dt><dd>{provider.data_policy} / {provider.tls_policy}</dd></div><div><dt>Capabilities</dt><dd>{[provider.capabilities.streaming && "streaming", provider.capabilities.tool_calls && "tools", provider.capabilities.structured_output && "structured output"].filter(Boolean).join(", ") || "basic completion"}</dd></div><div><dt>Last test</dt><dd>{provider.last_test_status ? `${provider.last_test_status}${provider.last_test_latency_ms === null ? "" : ` · ${provider.last_test_latency_ms} ms`}` : "Not tested"}</dd></div></dl>
                <div className="provider-actions"><button disabled={testProvider.isPending} type="button" onClick={() => testProvider.mutate(provider)}>{testProvider.isPending && testProvider.variables?.id === provider.id ? "Testing…" : `Test ${provider.display_name}`}</button><button disabled={updateProvider.isPending || (!status?.enabled && !provider.enabled)} type="button" onClick={() => updateProvider.mutate({ provider, changes: { enabled: !provider.enabled, ...(provider.enabled ? { is_default: false } : {}) } })}>{provider.enabled ? "Disable" : "Enable"}</button>{provider.enabled && !provider.is_default ? <button disabled={updateProvider.isPending} type="button" onClick={() => updateProvider.mutate({ provider, changes: { is_default: true } })}>Make default</button> : null}<button disabled={deleteProvider.isPending} type="button" onClick={() => { if (window.confirm(`Delete ${provider.display_name}?`)) deleteProvider.mutate(provider); }}>Delete</button></div>
                {result ? <p className={result.reachable && result.model_accepted ? "provider-test-ok" : "form-error"} role="status">{result.reachable && result.model_accepted ? `Connected · ${result.latency_ms ?? "—"} ms` : result.message}</p> : null}
              </li>
            );
          })}
        </ul>
        {providersQuery.isError ? <p className="form-error" role="alert">Provider profiles could not be loaded.</p> : null}
        {testProvider.isError ? <p className="form-error" role="alert">Provider testing failed safely. No provider payload was returned.</p> : null}
        {updateProvider.isError ? <p className="form-error" role="alert">The provider profile could not be updated.</p> : null}
        {deleteProvider.isError ? <p className="form-error" role="alert">The provider profile could not be deleted.</p> : null}
      </div>
    </section>
  );
}
