import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../app/api/client";
import { createQueryClient } from "../../app/query-client";
import type { InferenceProvider, InferenceSkill, InferenceStreamEvent } from "../../app/api/types";
import { AssistPanel } from "./AssistPanel";

const provider: InferenceProvider = {
  id: "provider-1",
  provider_identifier: "local-fake",
  display_name: "Local fake",
  base_url: "http://127.0.0.1:11434/v1",
  model_id: "fake-model",
  api_mode: "CHAT_COMPLETIONS",
  capabilities: { streaming: true, tool_calls: false, structured_output: true, embeddings: false, max_context_tokens: null },
  timeout_seconds: 30,
  tls_policy: "PLAINTEXT_LOCAL_ONLY",
  data_policy: "LOCAL_ONLY",
  secret_status: "NOT_REQUIRED",
  enabled: true,
  is_default: true,
  last_tested_at: null,
  last_test_status: null,
  last_test_latency_ms: null,
  revision: 1,
  created_at: "2026-08-24T00:00:00Z",
  updated_at: "2026-08-24T00:00:00Z",
};

const skill: InferenceSkill = {
  id: "draft-implementation-notes",
  version: "1.0.0",
  name: "Draft implementation notes",
  description: "Drafts implementation notes for review.",
  record_scopes: ["requirement"],
  writes_workspace: false,
  requires_confirmation: false,
  output_schema: {},
};

afterEach(() => vi.restoreAllMocks());

function mockQueries(currentProvider: InferenceProvider = provider, currentSkill: InferenceSkill = skill) {
  vi.spyOn(api, "get").mockImplementation((path) => Promise.resolve((
    path === "/inference/status"
      ? { enabled: true, ready: true, allowed_base_urls: [currentProvider.base_url], limits: { max_concurrent_runs: 2, max_context_chars: 60000, max_output_chars: 12000, max_iterations: 4, max_tool_calls: 8, timeout_seconds: 90 } }
      : path === "/inference/providers" ? [currentProvider]
        : [currentSkill]
  ) as never));
}

describe("AssistPanel", () => {
  it("previews exact context, streams a structured result, and applies only a local draft", async () => {
    const user = userEvent.setup();
    mockQueries();
    const post = vi.spyOn(api, "post").mockImplementation((path) => Promise.resolve((
      path === "/inference/context-preview" ? {
        text: "RECORD requirement:CC8.1\nDeployment changes are reviewed.",
        digest: "a".repeat(64),
        source_references: ["requirement:CC8.1"],
        omissions: [],
        selected_record_types: ["requirement"],
        typed_resource_text_included: true,
        attachment_bytes_included: false,
      } : {}
    ) as never));
    const patch = vi.spyOn(api, "patch");
    vi.spyOn(api, "stream").mockImplementation((_path, _body, onEvent) => {
      const events: InferenceStreamEvent[] = [
        { type: "run_started", run_id: "run-1" },
        { type: "status", status: "RUNNING" },
        { type: "text_delta", text: "Draft output" },
        { type: "proposal", proposal: { implementation_notes: "Changes are reviewed before deployment.", assumptions: [], missing_details: [], source_references: ["requirement:CC8.1"] } },
        { type: "completed", terminal_state: "COMPLETED", structured: true },
      ];
      events.forEach((event) => onEvent(event));
      return Promise.resolve();
    });
    const useImplementationDraft = vi.fn();
    render(
      <QueryClientProvider client={createQueryClient()}>
        <AssistPanel canEdit entityId="requirement-id" entityType="requirement" onImplementationDraft={useImplementationDraft} onResourceDraft={vi.fn()} />
      </QueryClientProvider>,
    );

    await user.selectOptions(await screen.findByLabelText("Skill"), skill.id);
    await user.selectOptions(screen.getByLabelText("Provider"), provider.id);
    await user.click(screen.getByRole("button", { name: "Preview exact context" }));
    expect(await screen.findByText(/Deployment changes are reviewed/)).toBeVisible();
    expect(screen.getByText("Stored attachment bytes excluded")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Run assistance" }));

    expect(await screen.findByText("Changes are reviewed before deployment.")).toBeVisible();
    expect(screen.getByText("requirement:CC8.1")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Use as implementation-note draft" }));
    expect(useImplementationDraft).toHaveBeenCalledWith("Changes are reviewed before deployment.");
    expect(patch).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Useful" }));
    expect(post).toHaveBeenCalledWith("/inference/runs/run-1/feedback", { rating: "USEFUL", comment: null });
  });

  it("requires fresh external confirmation and keeps unstructured output copy-only", async () => {
    const user = userEvent.setup();
    const external = { ...provider, id: "external-1", display_name: "Hosted provider", base_url: "https://models.example.test/v1", data_policy: "REDACTED_EXTERNAL" as const };
    const unstructuredSkill = { ...skill, id: "requirement-summary-next-actions", name: "Requirement summary" };
    mockQueries(external, unstructuredSkill);
    vi.spyOn(api, "post").mockResolvedValue({
      text: "Selected record context",
      digest: "b".repeat(64),
      source_references: ["requirement:CC8.1"],
      omissions: [],
      selected_record_types: ["requirement"],
      typed_resource_text_included: false,
      attachment_bytes_included: false,
    } as never);
    const stream = vi.spyOn(api, "stream").mockImplementation((_path, _body, onEvent) => {
      onEvent({ type: "run_started", run_id: "run-2" });
      onEvent({ type: "text_delta", text: "Advice only" });
      onEvent({ type: "completed", terminal_state: "COMPLETED", structured: false });
      return Promise.resolve();
    });
    render(
      <QueryClientProvider client={createQueryClient()}>
        <AssistPanel canEdit entityId="requirement-id" entityType="requirement" onImplementationDraft={vi.fn()} onResourceDraft={vi.fn()} />
      </QueryClientProvider>,
    );

    await user.selectOptions(await screen.findByLabelText("Skill"), unstructuredSkill.id);
    await user.selectOptions(screen.getByLabelText("Provider"), external.id);
    await user.click(screen.getByRole("button", { name: "Preview exact context" }));
    expect(await screen.findByText(external.base_url)).toBeVisible();
    expect(screen.getByRole("button", { name: "Run assistance" })).toBeDisabled();
    await user.click(screen.getByLabelText("I confirm this context may be sent to the selected external provider for this run."));
    await user.click(screen.getByRole("button", { name: "Run assistance" }));

    await waitFor(() => expect(stream).toHaveBeenCalledWith(
      "/inference/runs/stream",
      expect.objectContaining({ external_transfer_confirmed: true }),
      expect.any(Function),
      expect.any(AbortSignal),
    ));
    expect(await screen.findByText("Unstructured advice-only result")).toBeVisible();
    expect(screen.getByRole("button", { name: "Copy result" })).toBeVisible();
    expect(screen.queryByRole("button", { name: /Use as/ })).not.toBeInTheDocument();
  });

  it("stops an active stream with a terminal cancelled state", async () => {
    const user = userEvent.setup();
    mockQueries();
    vi.spyOn(api, "post").mockResolvedValue({
      text: "Selected record context",
      digest: "c".repeat(64),
      source_references: ["requirement:CC8.1"],
      omissions: [],
      selected_record_types: ["requirement"],
      typed_resource_text_included: false,
      attachment_bytes_included: false,
    } as never);
    vi.spyOn(api, "stream").mockImplementation((_path, _body, _onEvent, signal) => new Promise((_resolve, reject) => {
      signal?.addEventListener("abort", () => reject(new DOMException("Stopped", "AbortError")));
    }));
    render(
      <QueryClientProvider client={createQueryClient()}>
        <AssistPanel canEdit entityId="requirement-id" entityType="requirement" onImplementationDraft={vi.fn()} onResourceDraft={vi.fn()} />
      </QueryClientProvider>,
    );

    await user.selectOptions(await screen.findByLabelText("Skill"), skill.id);
    await user.selectOptions(screen.getByLabelText("Provider"), provider.id);
    await user.click(screen.getByRole("button", { name: "Preview exact context" }));
    await user.click(await screen.findByRole("button", { name: "Run assistance" }));
    await user.click(await screen.findByRole("button", { name: "Stop assistance" }));
    expect(await screen.findByText("Cancelled")).toBeVisible();
  });
});
