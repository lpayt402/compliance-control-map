import { expect, test, type Page, type Route } from "@playwright/test";

const skills = [
  { id: "requirement-summary-next-actions", version: "1.0.0", name: "Requirement Summary and Next Actions", description: "Summary", record_scopes: ["requirement"], writes_workspace: false, requires_confirmation: false, output_schema: {} },
  { id: "draft-implementation-notes", version: "1.0.0", name: "Draft Implementation Notes", description: "Notes", record_scopes: ["requirement", "control"], writes_workspace: false, requires_confirmation: false, output_schema: {} },
  { id: "draft-evidence-playbook", version: "1.0.0", name: "Draft Evidence-Collection Playbook", description: "Playbook", record_scopes: ["requirement", "control"], writes_workspace: false, requires_confirmation: false, output_schema: {} },
  { id: "control-review", version: "1.0.0", name: "Control Review", description: "Control review", record_scopes: ["control"], writes_workspace: false, requires_confirmation: false, output_schema: {} },
];

const provider = {
  id: "e2e-provider", provider_identifier: "e2e-fake", display_name: "Deterministic fake", base_url: "http://host.docker.internal:11434/v1", model_id: "fake-model",
  api_mode: "CHAT_COMPLETIONS", capabilities: { streaming: true, tool_calls: true, structured_output: true, embeddings: false, max_context_tokens: 32000 }, timeout_seconds: 30,
  tls_policy: "PLAINTEXT_LOCAL_ONLY", data_policy: "LOCAL_ONLY", secret_status: "NOT_REQUIRED", enabled: true, is_default: false,
  last_tested_at: null, last_test_status: null, last_test_latency_ms: null, revision: 1, created_at: "2026-08-24T00:00:00Z", updated_at: "2026-08-24T00:00:00Z",
};
const runStamp = Date.now().toString(36);
const requirementDraft = `E2E proposal ${runStamp}: changes are approved and reviewed before deployment.`;
const playbookTitle = `E2E evidence playbook ${runStamp}`;
const controlDraft = `E2E control proposal ${runStamp}: review access quarterly and retain sign-off.`;

function json(route: Route, data: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify({ data, meta: {} }) });
}

function requestBody(route: Route): Record<string, unknown> {
  const value: unknown = route.request().postDataJSON();
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function recordKind(body: Record<string, unknown>): "requirement" | "control" {
  const references = body.record_references;
  if (!Array.isArray(references)) return "requirement";
  const first: unknown = references[0];
  if (first === null || typeof first !== "object") return "requirement";
  return (first as Record<string, unknown>).kind === "control" ? "control" : "requirement";
}

async function installFakeProvider(page: Page) {
  let profiles: typeof provider[] = [];
  await page.route("**/api/v1/inference/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1/inference", "");
    if (path === "/status") return json(route, { enabled: true, ready: true, allowed_base_urls: [provider.base_url], limits: { max_concurrent_runs: 2, max_context_chars: 60000, max_output_chars: 12000, max_iterations: 4, max_tool_calls: 8, timeout_seconds: 90 } });
    if (path === "/skills") return json(route, skills);
    if (path === "/providers" && request.method() === "GET") return json(route, profiles);
    if (path === "/providers" && request.method() === "POST") {
      const body = requestBody(route);
      profiles = [{ ...provider, enabled: body.enabled === true, is_default: body.is_default === true }];
      return json(route, profiles[0], 201);
    }
    if (path === `/providers/${provider.id}/test`) return json(route, { reachable: true, model_accepted: true, latency_ms: 7, error_code: null, message: "Provider and configured model responded successfully." });
    if (path === "/runs") return json(route, []);
    if (path.endsWith("/feedback")) return json(route, { feedback_rating: requestBody(route).rating });
    if (path === "/context-preview") {
      const body = requestBody(route);
      const kind = recordKind(body);
      return json(route, { text: `UNTRUSTED WORKSPACE DATA\nSelected ${kind} facts only.`, digest: "d".repeat(64), source_references: [kind === "control" ? "control:AC-01" : "requirement:CC8.1"], omissions: [], selected_record_types: [kind], typed_resource_text_included: body.include_text_resources === true, attachment_bytes_included: false });
    }
    if (path === "/runs/stream") {
      const body = requestBody(route);
      const source = recordKind(body) === "control" ? "control:AC-01" : "requirement:CC8.1";
      if (body.instruction === "cancel this run") {
        await new Promise((resolve) => setTimeout(resolve, 5_000));
        try { return await route.abort(); } catch { return; }
      }
      const events = body.instruction === "simulate timeout"
        ? [{ type: "run_started", run_id: "run-timeout" }, { type: "error", terminal_state: "TIMED_OUT", error_code: "RUN_TIMEOUT", message: "The assistance run timed out." }]
        : body.skill_id === "draft-implementation-notes"
          ? [{ type: "run_started", run_id: "run-notes" }, { type: "text_delta", text: "Drafting from selected facts." }, { type: "proposal", proposal: { implementation_notes: requirementDraft, assumptions: [], missing_details: [], source_references: [source] } }, { type: "completed", terminal_state: "COMPLETED", structured: true }]
          : body.skill_id === "draft-evidence-playbook"
            ? [{ type: "run_started", run_id: "run-playbook" }, { type: "text_delta", text: "Drafting a playbook." }, { type: "proposal", proposal: { title: playbookTitle, objective: "Collect change approval evidence.", prerequisites: ["Approved change register"], steps: ["Export approved changes", "Retain reviewer sign-off"], expected_artifacts: ["Signed review"], validation_checks: ["Match deployments"], contacts_and_questions: [], source_references: [source] } }, { type: "completed", terminal_state: "COMPLETED", structured: true }]
            : body.skill_id === "control-review"
              ? [{ type: "run_started", run_id: "run-control" }, { type: "text_delta", text: "Reviewing the selected control." }, { type: "proposal", proposal: { summary: "The control has defined operation details.", wording_suggestions: [], missing_operating_detail: [], implementation_note_draft: controlDraft, evidence_categories: ["Reviewer sign-off"], source_references: [source] } }, { type: "completed", terminal_state: "COMPLETED", structured: true }]
              : [{ type: "run_started", run_id: "run-summary" }, { type: "text_delta", text: "Streaming a bounded summary." }, { type: "proposal", proposal: { summary: "Change approvals are documented.", known_facts: ["Selected requirement only"], missing_information: [], suggested_next_actions: ["Confirm retained samples"], source_references: [source], limitations: ["No audit assurance"] } }, { type: "completed", terminal_state: "COMPLETED", structured: true }];
      return route.fulfill({ status: 200, contentType: "application/x-ndjson", body: events.map((event) => JSON.stringify(event)).join("\n") + "\n" });
    }
    return route.abort();
  });
}

async function previewAndRun(page: Page, skillId: string, instruction = "") {
  const assist = page.getByLabel("Optional model assistance");
  await assist.getByLabel("Skill").selectOption(skillId);
  await assist.getByLabel("Provider").selectOption(provider.id);
  await assist.getByLabel("Optional instruction").fill(instruction);
  await assist.getByRole("button", { name: "Preview exact context" }).click();
  await expect(assist.getByText("Stored attachment bytes excluded")).toBeVisible();
  await assist.getByRole("button", { name: "Run assistance" }).click();
  return assist;
}

test("optional assistance streams deterministic drafts without bypassing normal saves", async ({ page }) => {
  await installFakeProvider(page);

  await page.goto("/settings");
  await page.getByRole("button", { name: "Add provider" }).click();
  await page.getByLabel("Profile ID").fill("e2e-fake");
  await page.getByLabel("Display name").fill(provider.display_name);
  await page.getByLabel("Base URL").fill(provider.base_url);
  await page.getByLabel("Model ID").fill(provider.model_id);
  await page.getByLabel("TLS policy").selectOption("PLAINTEXT_LOCAL_ONLY");
  await page.getByLabel("Enable this profile after saving").check();
  await page.getByRole("button", { name: "Save provider" }).click();
  await page.getByRole("button", { name: `Test ${provider.display_name}` }).click();
  await expect(page.getByText("Connected · 7 ms")).toBeVisible();

  await page.getByRole("link", { name: "Framework map" }).click();
  await page.getByRole("searchbox", { name: "Find a requirement" }).fill("CC8.1");
  await page.getByRole("button", { name: /CC8\.1,/ }).click();
  const tabs = page.getByRole("tablist", { name: "Requirement sections" });
  const initialRecord = await page.request.get("/api/v1/requirements?search=CC8.1").then((response) => response.json()) as { data: Array<{ assessment: { implementation_notes: string } }> };

  await tabs.getByRole("tab", { name: "Assist" }).click();
  let assist = await previewAndRun(page, "requirement-summary-next-actions");
  await expect(assist.getByText("Change approvals are documented.")).toBeVisible();
  await expect(assist.getByText("requirement:CC8.1")).toBeVisible();

  assist = await previewAndRun(page, "draft-implementation-notes");
  await assist.getByRole("button", { name: "Use as implementation-note draft" }).click();
  await expect(page.getByLabel("Implementation notes")).toHaveValue(requirementDraft);
  const beforeSave = await page.request.get("/api/v1/requirements?search=CC8.1").then((response) => response.json()) as typeof initialRecord;
  expect(beforeSave.data[0]?.assessment.implementation_notes).toBe(initialRecord.data[0]?.assessment.implementation_notes);
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Saved", { exact: true })).toBeVisible();

  await tabs.getByRole("tab", { name: "Assist" }).click();
  assist = await previewAndRun(page, "draft-evidence-playbook");
  await assist.getByRole("button", { name: "Use as playbook draft" }).click();
  await expect(page.getByLabel("Resource type")).toHaveValue("PLAYBOOK");
  await expect(page.getByLabel("Title")).toHaveValue(playbookTitle);
  await page.getByRole("button", { name: "Save resource" }).click();
  await expect(page.getByText(playbookTitle, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close requirement details" }).click();

  await page.getByRole("searchbox", { name: "Find a requirement" }).fill("CC6.1");
  await page.getByRole("button", { name: /CC6\.1,/ }).click();
  const controlTabs = page.getByRole("tablist", { name: "Requirement sections" });
  await controlTabs.getByRole("tab", { name: "Controls" }).click();
  await page.getByRole("button", { name: /AC-01.*Open control/ }).click();
  const detailTabs = page.getByRole("tablist", { name: "Control sections" });
  await detailTabs.getByRole("tab", { name: "Assist" }).click();
  assist = await previewAndRun(page, "control-review");
  await assist.getByRole("button", { name: "Use as implementation-note draft" }).click();
  const controlForm = page.locator(".control-detail-form");
  await expect(controlForm.getByLabel("Implementation notes")).toHaveValue(controlDraft);
  await controlForm.getByRole("button", { name: "Save control changes" }).click();

  await detailTabs.getByRole("tab", { name: "Assist" }).click();
  assist = await previewAndRun(page, "control-review", "cancel this run");
  await assist.getByRole("button", { name: "Stop assistance" }).click();
  await expect(assist.getByText("Cancelled", { exact: true })).toBeVisible();
  assist = await previewAndRun(page, "control-review", "simulate timeout");
  await expect(assist.getByText("Timed out", { exact: true })).toBeVisible();

  const widths = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.client + 1);
});
