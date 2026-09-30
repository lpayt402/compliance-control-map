import { expect, test } from "@playwright/test";
import { stat } from "node:fs/promises";
import path from "node:path";

const policyFile = path.resolve(process.cwd(), "../backend/demo-files/demo-access-policy.txt");
const evidenceFile = path.resolve(
  process.cwd(),
  "../backend/demo-files/demo-quarterly-access-review.txt",
);

test.describe.serial("local compliance workspace", () => {
  test("assesses, controls, maps files, tracks, and exports", async ({ page }) => {
    await page.goto("/frameworks/soc2/map");

    await page.getByRole("searchbox", { name: "Find a requirement" }).fill("CC8.1");
    await expect(page.getByRole("status")).toHaveText("1 requirement shown");
    await page.getByRole("button", { name: "Clear filters" }).click();

    await page.getByRole("button", { name: /CC8\.1,/ }).click();
    await page.getByLabel("Readiness").selectOption("READY");
    await page
      .getByRole("dialog")
      .getByRole("combobox", { name: /^Owner$/ })
      .selectOption({ label: "Demo Control Owner" });
    await page.getByLabel("Due date").fill("2026-12-15");
    await page
      .getByLabel("Implementation notes")
      .fill("Changes are approved, tested, deployed, and reviewed with retained evidence.");
    const saveRequirement = page.getByRole("button", { name: "Save changes" });
    if (await saveRequirement.isEnabled()) {
      await saveRequirement.click();
      await expect(page.getByText("Saved", { exact: true })).toBeVisible();
    } else {
      await expect(page.getByText("No pending changes", { exact: true })).toBeVisible();
    }

    const requirementTabs = page.getByRole("tablist", { name: "Requirement sections" });
    await requirementTabs.getByRole("tab", { name: "Resources" }).click();
    await expect(page.getByText("Loading text resources…")).toHaveCount(0);
    if (await page.getByText("Normal assessment context retained for the change review.", { exact: true }).count() === 0) {
      await page.getByRole("button", { name: "Add text resource" }).click();
      await page.getByLabel("Text").fill("Normal assessment context retained for the change review.");
      await page.getByRole("button", { name: "Save resource" }).click();
    }
    await expect(page.getByText("Normal assessment context retained for the change review.").first()).toBeVisible();

    if (await page.getByText("Change evidence collection", { exact: true }).count() === 0) {
      await page.getByRole("button", { name: "Add text resource" }).click();
      await page.getByLabel("Resource type").selectOption("PLAYBOOK");
      await page.getByLabel("Title").fill("Change evidence collection");
      await page.getByLabel("Text").fill("1. Export approved changes.\n2. Match approvals to deployments.\n3. Retain reviewer sign-off.");
      await page.getByRole("button", { name: "Save resource" }).click();
    }
    await expect(page.getByText("Change evidence collection", { exact: true })).toBeVisible();

    if (await page.getByText("Change review owner", { exact: true }).count() === 0) {
      await page.getByRole("button", { name: "Add text resource" }).click();
      await page.getByLabel("Resource type").selectOption("CONTACT");
      await page.getByLabel("Title").fill("Change review owner");
      await page.getByLabel("Workspace contact").selectOption({ label: "Demo Control Owner" });
      await page.getByLabel("Text").fill("Coordinate questions about approvals and deployment evidence.");
      await page.getByRole("button", { name: "Save resource" }).click();
    }
    await expect(page.getByText("Change review owner", { exact: true })).toBeVisible();

    await requirementTabs.getByRole("tab", { name: "Controls" }).click();
    if (await page.getByText("CHG-01", { exact: true }).count() === 0) {
      await page.getByRole("button", { name: "Create control" }).click();
      await page.getByLabel("Control code").fill("CHG-01");
      await page.getByLabel("Control name").fill("Controlled production changes");
      await page
        .getByLabel("Description")
        .fill("Authorize, test, approve, and retain proof for production changes.");
      await page.getByRole("button", { name: "Save control" }).click();
    }
    await expect(page.getByText("CHG-01", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: /CHG-01.*Open control/ }).click();
    const controlForm = page.locator(".control-detail-form");
    await controlForm.getByLabel("Operating status").selectOption("OPERATING");
    await controlForm.getByLabel("Implementation notes").fill("Security reviews production changes and retains approvals.");
    await controlForm.getByLabel("Tags").fill("change, approval, production");
    const saveControl = controlForm.getByRole("button", { name: "Save control changes" });
    if (await saveControl.isEnabled()) {
      await saveControl.click();
      await expect(controlForm.getByText("Saved", { exact: true })).toBeVisible();
    } else {
      await expect(controlForm.getByText("No pending changes", { exact: true })).toBeVisible();
    }

    const controlTabs = page.getByRole("tablist", { name: "Control sections" });
    await controlTabs.getByRole("tab", { name: "Resources" }).click();
    await expect(page.getByText("Loading text resources…")).toHaveCount(0);
    if (await page.getByText("Control operation playbook", { exact: true }).count() === 0) {
      await page.getByRole("button", { name: "Add text resource" }).click();
      await page.getByLabel("Resource type").selectOption("PLAYBOOK");
      await page.getByLabel("Title").fill("Control operation playbook");
      await page.getByLabel("Text").fill("Review the change register and retain the signed exception report.");
      await page.getByRole("button", { name: "Save resource" }).click();
    }
    await expect(page.getByText("Control operation playbook", { exact: true })).toBeVisible();

    if (await page.locator(".resource-files").getByText("E2E Change Management Policy", { exact: true }).count() === 0) {
      const documentLibrary = await page.request.get("/api/v1/documents");
      const existingDocuments = await documentLibrary.json() as { data: Array<{ name: string }> };
      if (existingDocuments.data.some((item) => item.name === "E2E Change Management Policy")) {
        await page.getByLabel("Link existing document").selectOption({ label: "E2E Change Management Policy" });
        await page.getByRole("button", { name: "Link document" }).click();
      } else {
        await page.getByRole("button", { name: "Upload new document" }).click();
        const documentDialog = page.getByRole("dialog", { name: "Upload document" });
        await expect(documentDialog.getByText("This upload will be attached to 1 selected targets.")).toBeVisible();
        await documentDialog.getByLabel("Name").fill("E2E Change Management Policy");
        await documentDialog.getByLabel("File").setInputFiles(policyFile);
        await documentDialog.getByLabel("Description").fill("Policy used by the complete browser workflow.");
        await documentDialog.getByRole("button", { name: "Upload", exact: true }).click();
      }
    }
    await expect(page.locator(".resource-files").getByText("E2E Change Management Policy", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Back to mapped controls" }).click();
    await requirementTabs.getByRole("tab", { name: "Resources" }).click();
    if (await page.locator(".resource-files").getByText("E2E Change Management Policy", { exact: true }).count() === 0) {
      await page.getByLabel("Link existing document").selectOption({ label: "E2E Change Management Policy" });
      await page.getByRole("button", { name: "Link document" }).click();
    }
    await expect(page.locator(".resource-files").getByText("E2E Change Management Policy", { exact: true })).toBeVisible();

    if (await page.locator(".resource-files").getByText("E2E Change Approval Evidence", { exact: true }).count() === 0) {
      await page.getByRole("button", { name: "Upload new evidence" }).click();
      const evidenceDialog = page.getByRole("dialog", { name: "Upload evidence" });
      await evidenceDialog.getByLabel("Name").fill("E2E Change Approval Evidence");
      await evidenceDialog.getByLabel("File").setInputFiles(evidenceFile);
      await evidenceDialog.getByLabel("Evidence date").fill("2026-08-21");
      await evidenceDialog.getByRole("checkbox", { name: /CHG-01 Controlled production changes/ }).check();
      await evidenceDialog.getByRole("button", { name: "Upload", exact: true }).click();
    }
    await expect(page.locator(".resource-files").getByText("E2E Change Approval Evidence", { exact: true })).toBeVisible();

    await requirementTabs.getByRole("tab", { name: "Controls" }).click();
    await page.getByRole("button", { name: /CHG-01.*Open control/ }).click();
    await page.getByRole("tablist", { name: "Control sections" }).getByRole("tab", { name: "Resources" }).click();
    await expect(page.locator(".resource-files").getByText("E2E Change Approval Evidence", { exact: true })).toBeVisible();
    const controlDocument = page.locator(".resource-files").getByText("E2E Change Management Policy", { exact: true });
    if (await controlDocument.count() > 0) {
      page.once("dialog", (dialog) => dialog.accept());
      await controlDocument.locator("..").locator("..").getByRole("button", { name: "Detach" }).click();
    }
    await expect(page.locator(".resource-files").getByText("E2E Change Management Policy", { exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Back to mapped controls" }).click();
    await requirementTabs.getByRole("tab", { name: "Resources" }).click();
    await expect(page.locator(".resource-files").getByText("E2E Change Management Policy", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Close requirement details" }).click();

    await page.getByRole("link", { name: "Documents" }).click();
    await page.getByText("E2E Change Management Policy", { exact: true }).click();
    await expect(page.getByRole("complementary", { name: "E2E Change Management Policy details" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Requirement coverage/ })).toContainText("1");
    await expect(page.getByRole("heading", { name: /Control coverage/ })).toContainText("0");

    await page.getByRole("link", { name: "Evidence" }).click();
    await page.getByText("E2E Change Approval Evidence", { exact: true }).click();
    await expect(page.getByRole("complementary", { name: "E2E Change Approval Evidence details" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Requirement coverage/ })).toContainText("1");
    await expect(page.getByRole("heading", { name: /Control coverage/ })).toContainText("1");

    await page.getByRole("link", { name: "Framework map" }).click();
    await page.getByRole("searchbox", { name: "Find a requirement" }).fill("CC8.1");
    await page.getByRole("button", { name: /CC8\.1, Ready, 1 document, 1 evidence item, 1 control/ }).click();
    await page.getByRole("tablist", { name: "Requirement sections" }).getByRole("tab", { name: "Resources" }).click();
    await expect(page.locator(".resource-files").getByText("E2E Change Management Policy", { exact: true })).toBeVisible();
    await expect(page.locator(".resource-files").getByText("E2E Change Approval Evidence", { exact: true })).toBeVisible();
    await expect(page.getByText("Change evidence collection", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Close requirement details" }).click();

    await page.getByRole("link", { name: "Tracker" }).click();
    await page.getByLabel("Search").fill("CC8.1");
    await expect(page.getByLabel("Readiness for CC8.1")).toHaveValue("READY");
    await page.getByLabel("Search").fill("CC7.2");
    await page.getByLabel("Readiness for CC7.2").selectOption("PARTIAL");
    await expect(page.getByLabel("Readiness for CC7.2")).toHaveValue("PARTIAL");

    await page.getByRole("link", { name: "Dashboard" }).click();
    await expect(page.getByText(/2 Ready ÷ 61 applicable requirements/)).toBeVisible();
    await expect(page.getByText("3% ready", { exact: true })).toBeVisible();

    await page.getByRole("link", { name: "Settings" }).click();
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Create backup" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/^compliance-control-backup-.*\.zip$/);
    const downloadPath = await download.path();
    expect(downloadPath).not.toBeNull();
    expect((await stat(downloadPath)).size).toBeGreaterThan(1_000);
  });
});
