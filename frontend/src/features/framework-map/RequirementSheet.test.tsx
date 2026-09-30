import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../app/api/client";
import { createQueryClient } from "../../app/query-client";
import { SessionContext } from "../../app/session/session-context";
import { RequirementSheet } from "./RequirementSheet";
import { requirementFixture } from "./test-fixtures";

afterEach(() => vi.restoreAllMocks());

describe("RequirementSheet", () => {
  it("uses a focused modal sheet with an optional editor assistance tab", async () => {
    const user = userEvent.setup();
    const requirement = requirementFixture();
    vi.spyOn(api, "get").mockResolvedValue([]);
    const onOpenChange = vi.fn();
    render(
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter>
          <button>Origin tile</button>
          <RequirementSheet open onOpenChange={onOpenChange} requirement={requirement} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const dialog = screen.getByRole("dialog", { name: /AC-1/ });
    expect(dialog).toHaveClass("requirement-sheet");
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "Overview",
      "Controls",
      "Resources",
      "Assist",
      "Activity",
    ]);
    await user.keyboard("{Escape}");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("protects an assessment draft when switching tabs", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "get").mockResolvedValue([]);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter>
          <RequirementSheet open onOpenChange={vi.fn()} requirement={requirementFixture()} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await user.type(screen.getByLabelText("Implementation notes"), " Updated");
    await user.click(screen.getByRole("tab", { name: "Resources" }));
    expect(confirm).toHaveBeenCalledWith("Discard unsaved changes?");
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
  });

  it("synchronizes not-applicable fields and saves an explicit draft", async () => {
    const user = userEvent.setup();
    const requirement = requirementFixture();
    vi.spyOn(api, "get").mockResolvedValue([]);
    const patch = vi.spyOn(api, "patch").mockResolvedValue({
      ...requirement,
      assessment: {
        ...requirement.assessment,
        status_code: "NOT_APPLICABLE",
        applicability: "NOT_APPLICABLE",
        revision: 2,
      },
    });
    render(
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter>
          <RequirementSheet open onOpenChange={vi.fn()} requirement={requirement} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await user.selectOptions(screen.getByLabelText("Readiness"), "NOT_APPLICABLE");
    expect(screen.getByLabelText("Applicability")).toHaveValue("NOT_APPLICABLE");
    expect(screen.getByText("Unsaved")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(patch).toHaveBeenCalledWith(
      "/requirements/id-AC-1/assessment",
      expect.objectContaining({
        status_code: "NOT_APPLICABLE",
        applicability: "NOT_APPLICABLE",
        revision: 1,
      }),
    );
    expect(await screen.findByText("Saved")).toBeVisible();
  });

  it("creates and maps an organizational control without copying requirement status", async () => {
    const user = userEvent.setup();
    const requirement = requirementFixture();
    vi.spyOn(api, "get").mockResolvedValue([]);
    const post = vi.spyOn(api, "post")
      .mockResolvedValueOnce({ id: "control-1", code: "AC-01", name: "Access lifecycle", status_code: "PLANNED" })
      .mockResolvedValueOnce({ id: "mapping-1", control_id: "control-1" });
    render(
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter><RequirementSheet open onOpenChange={vi.fn()} requirement={requirement} /></MemoryRouter>
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole("tab", { name: "Controls" }));
    await user.click(screen.getByRole("button", { name: "Create control" }));
    await user.type(screen.getByLabelText("Control code"), "AC-01");
    await user.type(screen.getByLabelText("Control name"), "Access lifecycle");
    await user.click(screen.getByRole("button", { name: "Save control" }));

    expect(post).toHaveBeenNthCalledWith(1, "/controls", expect.objectContaining({ code: "AC-01", name: "Access lifecycle" }));
    expect(post).toHaveBeenNthCalledWith(2, "/requirements/id-AC-1/controls", { control_id: "control-1", coverage: "PRIMARY", rationale: "" });
  });

  it("keeps an assistance proposal local until the normal assessment save", async () => {
    const user = userEvent.setup();
    const requirement = requirementFixture();
    const provider = {
      id: "provider-1", provider_identifier: "fake", display_name: "Local fake", base_url: "http://127.0.0.1:11434/v1", model_id: "fake-model",
      api_mode: "CHAT_COMPLETIONS", capabilities: { streaming: true, tool_calls: false, structured_output: true, embeddings: false, max_context_tokens: null }, timeout_seconds: 30,
      tls_policy: "PLAINTEXT_LOCAL_ONLY", data_policy: "LOCAL_ONLY", secret_status: "NOT_REQUIRED", enabled: true, is_default: true,
      last_tested_at: null, last_test_status: null, last_test_latency_ms: null, revision: 1, created_at: "2026-08-24T00:00:00Z", updated_at: "2026-08-24T00:00:00Z",
    };
    vi.spyOn(api, "get").mockImplementation((path) => Promise.resolve((
      path === "/inference/status" ? { enabled: true, ready: true, allowed_base_urls: [provider.base_url], limits: { max_concurrent_runs: 2, max_context_chars: 60000, max_output_chars: 12000, max_iterations: 4, max_tool_calls: 8, timeout_seconds: 90 } }
        : path === "/inference/providers" ? [provider]
          : path === "/inference/skills" ? [{ id: "draft-implementation-notes", version: "1.0.0", name: "Draft implementation notes", description: "Draft", record_scopes: ["requirement"], writes_workspace: false, requires_confirmation: false, output_schema: {} }]
            : []
    ) as never));
    vi.spyOn(api, "post").mockResolvedValue({ text: "Exact selected record", digest: "a".repeat(64), source_references: ["requirement:AC-1"], omissions: [], selected_record_types: ["requirement"], typed_resource_text_included: false, attachment_bytes_included: false } as never);
    vi.spyOn(api, "stream").mockImplementation((_path, _body, onEvent) => {
      onEvent({ type: "run_started", run_id: "run-1" });
      onEvent({ type: "proposal", proposal: { implementation_notes: "Human-review draft.", assumptions: [], missing_details: [], source_references: ["requirement:AC-1"] } });
      onEvent({ type: "completed", terminal_state: "COMPLETED", structured: true });
      return Promise.resolve();
    });
    const patch = vi.spyOn(api, "patch").mockResolvedValue({ ...requirement, assessment: { ...requirement.assessment, implementation_notes: "Human-review draft.", revision: 2 } });
    render(<QueryClientProvider client={createQueryClient()}><MemoryRouter><RequirementSheet open onOpenChange={vi.fn()} requirement={requirement} /></MemoryRouter></QueryClientProvider>);

    await user.click(screen.getByRole("tab", { name: "Assist" }));
    await user.selectOptions(await screen.findByLabelText("Skill"), "draft-implementation-notes");
    await user.selectOptions(screen.getByLabelText("Provider"), "provider-1");
    await user.click(screen.getByRole("button", { name: "Preview exact context" }));
    await user.click(await screen.findByRole("button", { name: "Run assistance" }));
    await user.click(await screen.findByRole("button", { name: "Use as implementation-note draft" }));

    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Implementation notes")).toHaveValue("Human-review draft.");
    expect(patch).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(patch).toHaveBeenCalledWith("/requirements/id-AC-1/assessment", expect.objectContaining({ implementation_notes: "Human-review draft.", revision: 1 }));
  });

  it("does not expose assistance initiation to a Viewer", () => {
    vi.spyOn(api, "get").mockResolvedValue([]);
    render(
      <QueryClientProvider client={createQueryClient()}>
        <SessionContext.Provider value={{ user: { id: "viewer", display_name: "Viewer", email: null, role: "VIEWER" }, status: "authenticated", setUser: vi.fn(), setStatus: vi.fn() }}>
          <MemoryRouter><RequirementSheet open onOpenChange={vi.fn()} requirement={requirementFixture()} /></MemoryRouter>
        </SessionContext.Provider>
      </QueryClientProvider>,
    );

    expect(screen.queryByRole("tab", { name: "Assist" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run assistance" })).not.toBeInTheDocument();
  });
});
