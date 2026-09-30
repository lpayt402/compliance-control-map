import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../app/api/client";
import { createQueryClient } from "../../app/query-client";
import { SessionContext } from "../../app/session/session-context";
import { SettingsPage } from "./SettingsPage";

afterEach(() => vi.restoreAllMocks());

describe("SettingsPage", () => {
  it("gates provider and other administrative actions", async () => {
    vi.spyOn(api, "get").mockImplementation((path) => Promise.resolve(path === "/users" ? [] : [{ slug: "soc2", name: "SOC 2 Trust Services Criteria", active_version: null }]));
    render(
      <QueryClientProvider client={createQueryClient()}>
        <SessionContext.Provider value={{
          user: { id: "viewer", display_name: "View only", email: "viewer@example.test", role: "VIEWER" },
          status: "authenticated",
          setUser: vi.fn(),
          setStatus: vi.fn(),
        }}>
          <MemoryRouter><SettingsPage /></MemoryRouter>
        </SessionContext.Provider>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Provider configuration is restricted to workspace administrators. Assistance never changes workspace records automatically.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Add provider" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create backup" })).not.toBeInTheDocument();
    expect(screen.getByText("Administrators can manage users and backups.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Change my password" })).toBeVisible();
  });

  it("lets an administrator manage account lifecycle and review access activity", async () => {
    const user = userEvent.setup();
    const users = [
      { id: "admin", display_name: "Local Admin", email: "admin@example.test", role: "ADMIN", is_disabled: false },
      { id: "viewer", display_name: "Evidence Viewer", email: "viewer@example.test", role: "VIEWER", is_disabled: true },
    ];
    vi.spyOn(api, "get").mockImplementation((path) => Promise.resolve(
      path === "/users" ? users
        : path === "/users/activity" ? [{
          id: "event-1",
          action_code: "USER_DEACTIVATED",
          entity_id: "viewer",
          actor_display_name: "Local Admin",
          before: { display_name: "Evidence Viewer", is_disabled: false },
          after: { display_name: "Evidence Viewer", is_disabled: true },
          created_at: "2026-08-23T12:00:00Z",
        }]
          : path === "/inference/status" ? { enabled: false, ready: false, allowed_base_urls: [], limits: { max_concurrent_runs: 2, max_context_chars: 60000, max_output_chars: 12000, max_iterations: 4, max_tool_calls: 8, timeout_seconds: 90 } }
            : path === "/inference/providers" ? []
              : [{ slug: "soc2", name: "SOC 2 Trust Services Criteria", active_version: null }],
    ));
    const patch = vi.spyOn(api, "patch").mockResolvedValue(users[1] as never);
    const remove = vi.spyOn(api, "delete").mockResolvedValue(undefined);
    const post = vi.spyOn(api, "post").mockResolvedValue(undefined);
    const setUser = vi.fn();
    const setStatus = vi.fn();
    render(
      <QueryClientProvider client={createQueryClient()}>
        <SessionContext.Provider value={{
          user: { id: "admin", display_name: "Local Admin", email: "admin@example.test", role: "ADMIN" },
          status: "authenticated",
          setUser,
          setStatus,
        }}>
          <MemoryRouter><SettingsPage /></MemoryRouter>
        </SessionContext.Provider>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Deactivated")).toBeVisible();
    expect(screen.getByText("Local Admin deactivated Evidence Viewer")).toBeVisible();
    expect(screen.getByRole("button", { name: "Deactivate Local Admin" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Edit Evidence Viewer" }));
    await user.selectOptions(screen.getByLabelText("Role"), "EDITOR");
    await user.click(screen.getByRole("button", { name: "Save user" }));
    expect(patch).toHaveBeenCalledWith("/users/viewer", expect.objectContaining({ role: "EDITOR" }));

    await user.click(screen.getByRole("button", { name: "Reset password for Evidence Viewer" }));
    await user.type(screen.getByLabelText("New password"), "a replacement viewer passphrase");
    await user.click(screen.getByRole("button", { name: "Set password" }));
    expect(patch).toHaveBeenCalledWith("/users/viewer", { password: "a replacement viewer passphrase" });

    await user.click(screen.getByRole("button", { name: "Reactivate Evidence Viewer" }));
    expect(patch).toHaveBeenCalledWith("/users/viewer", { is_disabled: false });

    await user.click(screen.getByRole("button", { name: "Delete Evidence Viewer" }));
    expect(screen.getByRole("dialog", { name: "Delete Evidence Viewer?" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Delete permanently" }));
    expect(remove).toHaveBeenCalledWith("/users/viewer");

    await user.type(screen.getByLabelText("Current password"), "a sturdy admin passphrase");
    await user.type(screen.getByLabelText("Your new password"), "a replacement admin passphrase");
    await user.click(screen.getByRole("button", { name: "Change my password" }));
    expect(post).toHaveBeenCalledWith("/auth/change-password", {
      current_password: "a sturdy admin passphrase",
      new_password: "a replacement admin passphrase",
    });
    expect(setUser).toHaveBeenCalledWith(null);
    expect(setStatus).toHaveBeenCalledWith("unauthenticated");
  });
});
