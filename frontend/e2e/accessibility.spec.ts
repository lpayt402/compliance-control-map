import { expect, test } from "@playwright/test";

test("map, modal, filters, table, and reflow expose their state", async ({ page }, testInfo) => {
  await page.goto("/frameworks/soc2/map");
  await expect(page.getByRole("status")).toHaveText("61 requirements shown");

  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to workspace" })).toBeFocused();

  const firstTile = page.getByRole("button", { name: /CC1\.1, Not assessed, 0 documents/ });
  const secondTile = page.getByRole("button", { name: /CC1\.2, Not assessed, 0 documents/ });
  await firstTile.focus();
  await firstTile.press("ArrowRight");
  await expect(secondTile).toBeFocused();
  await secondTile.click();

  const dialog = page.getByRole("dialog", { name: /CC1\.2/ });
  await expect(dialog).toBeVisible();
  await expect(page.getByRole("button", { name: "Close requirement details" })).toBeFocused();
  const desktopBox = await dialog.boundingBox();
  expect(desktopBox).not.toBeNull();
  expect(desktopBox!.width / page.viewportSize()!.width).toBeGreaterThan(0.68);
  expect(desktopBox!.width / page.viewportSize()!.width).toBeLessThan(0.82);
  await page.getByRole("button", { name: "Close requirement details" }).click();
  await expect(secondTile).toBeFocused();

  await page.getByRole("searchbox", { name: "Find a requirement" }).fill("CC8.1");
  await expect(page.getByRole("status")).toHaveText("1 requirement shown");
  await expect(page.getByRole("button", { name: /CC8\.1/ })).toBeVisible();

  await page.getByRole("link", { name: "Tracker" }).click();
  const identifierHeader = page.getByRole("columnheader", { name: /Sort by identifier/i });
  await expect(identifierHeader).toHaveAttribute("aria-sort", "ascending");
  await page.getByRole("button", { name: "Sort by title" }).click();
  await expect(page.getByRole("columnheader", { name: /Sort by title/i })).toHaveAttribute("aria-sort", "ascending");

  await page.setViewportSize({ width: 640, height: 900 });
  await page.getByRole("link", { name: "Framework map" }).click();
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
  await page.screenshot({ path: testInfo.outputPath("map-200-percent-equivalent.png"), fullPage: true });
});

const targetViewports = [
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
  { width: 1280, height: 720 },
  { width: 1024, height: 768 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
];

test("primary routes contain overflow at every target viewport", async ({ page }) => {
  for (const viewport of targetViewports) {
    await page.setViewportSize(viewport);
    for (const route of ["/", "/tracker", "/documents", "/evidence", "/settings"]) {
      await page.goto(route);
      const root = await page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      }));
      expect(root.scrollWidth, `${route} at ${viewport.width}x${viewport.height}`).toBeLessThanOrEqual(root.clientWidth + 1);
    }

    await page.goto("/frameworks/soc2/map");
    const atlas = page.locator(".framework-atlas");
    await expect(atlas).toBeVisible();
    const atlasMetrics = await atlas.evaluate((element) => ({
      clientHeight: element.clientHeight,
      clientWidth: element.clientWidth,
      scrollHeight: element.scrollHeight,
      scrollWidth: element.scrollWidth,
    }));
    expect(atlasMetrics.clientHeight).toBeLessThanOrEqual(viewport.height);
    expect(atlasMetrics.scrollWidth).toBeGreaterThan(atlasMetrics.clientWidth);
    const mapRootWidth = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(mapRootWidth).toBeLessThanOrEqual(1);

    await page.goto("/tracker");
    const tableWrapper = page.locator(".tracker-table-wrap");
    const tableMetrics = await tableWrapper.evaluate((element) => ({
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
    }));
    expect(tableMetrics.clientHeight).toBeLessThanOrEqual(viewport.height);
    expect(tableMetrics.scrollHeight).toBeGreaterThan(tableMetrics.clientHeight);
  }
});

test("long content wraps without hiding sheet or page controls", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/frameworks/soc2/map");
  await page.getByRole("button", { name: /CC1\.1/ }).click();
  await expect(page.locator(".requirement-sheet")).toHaveCSS("transform", "none");
  await page.locator(".sheet-header h2").evaluate((element) => {
    element.textContent = `CC1.1 ${"LongUnbrokenRequirementTitle".repeat(16)}`;
  });
  const closeBox = await page.getByRole("button", { name: "Close requirement details" }).boundingBox();
  expect(closeBox).not.toBeNull();
  expect(closeBox!.x + closeBox!.width).toBeLessThanOrEqual(390);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  await page.getByRole("button", { name: "Close requirement details" }).click();

  await page.getByRole("link", { name: "Documents" }).click();
  await page.locator(".library-index strong").first().evaluate((element) => {
    element.textContent = "LongUnbrokenDocumentName".repeat(20);
  });
  await page.locator(".library-index span").first().evaluate((element) => {
    element.textContent = "LongUnbrokenFilename".repeat(20);
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
});

test("resource and control subviews expose keyboard-readable state", async ({ page }) => {
  await page.goto("/frameworks/soc2/map");
  await page.getByRole("searchbox", { name: "Find a requirement" }).fill("CC6.1");
  await page.getByRole("button", { name: /CC6\.1/ }).click();
  await page.getByRole("tablist", { name: "Requirement sections" }).getByRole("tab", { name: "Resources" }).click();
  await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Notes \d+$/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Playbooks \d+$/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Contacts \d+$/ })).toBeVisible();
  await page.getByRole("tablist", { name: "Requirement sections" }).getByRole("tab", { name: "Controls" }).click();
  await page.getByRole("button", { name: /AC-01.*Open control/ }).click();
  await expect(page.getByLabel("Control code")).toBeVisible();
  await page.getByRole("tablist", { name: "Control sections" }).getByRole("tab", { name: "Resources" }).click();
  await expect(page.getByRole("heading", { name: "Notes, playbooks, and contacts" })).toBeVisible();
  await page.keyboard.press("Shift+Tab");
  await expect(page.locator(":focus-visible")).toHaveCount(1);
});
