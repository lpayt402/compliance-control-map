import { expect, test } from "@playwright/test";

const teamBaseUrl = process.env.CCM_E2E_TEAM_BASE_URL;
test.skip(!teamBaseUrl, "Team-mode credentials are supplied by the isolated server smoke test.");
test.use({ baseURL: teamBaseUrl ?? "http://127.0.0.1:3000" });

async function login(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Compliance Control Map" })).toBeVisible();
}

test("viewer sees the workspace without mutation controls", async ({ page }) => {
  await login(page, process.env.CCM_E2E_VIEWER_EMAIL!, process.env.CCM_E2E_VIEWER_PASSWORD!);
  await page.getByRole("link", { name: "Documents" }).click();
  await expect(page.getByRole("button", { name: "Upload document" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Download attachment" })).toBeVisible();
  await page.getByRole("link", { name: "Framework map" }).click();
  await page.getByRole("button", { name: /CC8\.1/ }).click();
  await expect(page.getByLabel("Readiness")).toBeDisabled();
  await expect(page.getByText(/Viewer access/)).toBeVisible();
  await expect(page.getByRole("tab", { name: "Assist" })).toHaveCount(0);
  await page.getByRole("tablist", { name: "Requirement sections" }).getByRole("tab", { name: "Resources" }).click();
  await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Add text resource" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Upload new/ })).toHaveCount(0);
});

test("editor can work but cannot administer", async ({ page }) => {
  await login(page, process.env.CCM_E2E_EDITOR_EMAIL!, process.env.CCM_E2E_EDITOR_PASSWORD!);
  await page.getByRole("link", { name: "Documents" }).click();
  await expect(page.getByRole("button", { name: "Upload document" })).toBeVisible();
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("button", { name: "Add user" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Create backup" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Change my password" })).toBeVisible();
});

test("admin manages the complete account lifecycle", async ({ page }) => {
  const accountName = "Browser lifecycle user";
  const accountEmail = `browser-lifecycle-${Date.now()}@example.com`;
  const accountPassword = "Browser lifecycle passphrase one";
  await login(page, process.env.CCM_E2E_ADMIN_EMAIL!, process.env.CCM_E2E_ADMIN_PASSWORD!);
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("button", { name: "Add user" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Create backup" })).toBeVisible();

  await page.getByRole("button", { name: "Add user" }).click();
  await page.getByLabel("Display name").fill(accountName);
  await page.getByLabel("Email").fill(accountEmail);
  await page.getByLabel("Initial password").fill(accountPassword);
  await page.getByLabel("Role").selectOption("VIEWER");
  await page.getByRole("button", { name: "Create user" }).click();

  const row = page.locator(".user-list > li").filter({ hasText: accountName });
  await expect(row).toContainText("VIEWER");
  await expect(page.getByText(`Smoke administrator created ${accountName}`)).toBeVisible();

  await row.getByRole("button", { name: `Edit ${accountName}` }).click();
  await page.getByRole("dialog", { name: `Edit ${accountName}` }).getByLabel("Role").selectOption("EDITOR");
  await page.getByRole("button", { name: "Save user" }).click();
  await expect(row).toContainText("EDITOR");

  await row.getByRole("button", { name: `Deactivate ${accountName}` }).click();
  await expect(row).toContainText("Deactivated");
  await row.getByRole("button", { name: `Reactivate ${accountName}` }).click();
  await expect(row).toContainText("Active");

  await row.getByRole("button", { name: `Reset password for ${accountName}` }).click();
  const resetDialog = page.getByRole("dialog", { name: `Reset password for ${accountName}` });
  await resetDialog.getByLabel("New password", { exact: true }).fill("Browser lifecycle passphrase two");
  await resetDialog.getByRole("button", { name: "Set password" }).click();
  await expect(page.getByText(`Smoke administrator reset the password for ${accountName}`)).toBeVisible();

  await row.getByRole("button", { name: `Delete ${accountName}` }).click();
  await expect(page.getByRole("dialog", { name: `Delete ${accountName}?` })).toBeVisible();
  await page.getByRole("button", { name: "Delete permanently" }).click();
  await expect(row).toHaveCount(0);
  await expect(page.getByText(`Smoke administrator deleted ${accountName}`)).toBeVisible();
});
