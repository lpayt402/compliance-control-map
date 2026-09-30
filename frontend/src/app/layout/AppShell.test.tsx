import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("presents the six primary destinations in order", () => {
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AppShell>
          <h1>Readiness desk</h1>
        </AppShell>
      </MemoryRouter>,
    );

    const navigation = screen.getByRole("navigation", { name: "Primary" });
    expect(within(navigation).getAllByRole("link").map((link) => link.textContent)).toEqual([
      "Dashboard",
      "Framework map",
      "Tracker",
      "Documents",
      "Evidence",
      "Settings",
    ]);
    expect(screen.getByRole("link", { name: "Skip to workspace" })).toHaveAttribute(
      "href",
      "#workspace",
    );
  });

  it("opens the command palette from the standard keyboard shortcut", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AppShell>
          <h1>Readiness desk</h1>
        </AppShell>
      </MemoryRouter>,
    );

    await user.keyboard("{Control>}k{/Control}");

    expect(screen.getByRole("dialog", { name: "Go somewhere" })).toBeVisible();
    expect(screen.getByRole("combobox", { name: "Find a page" })).toHaveFocus();
  });
});
