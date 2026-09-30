import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../app/api/client";
import { createQueryClient } from "../../app/query-client";
import { SessionContext } from "../../app/session/session-context";
import { LoginPage } from "./LoginPage";

afterEach(() => vi.restoreAllMocks());

describe("LoginPage", () => {
  it("starts a team session without storing the password", async () => {
    const user = userEvent.setup();
    const setUser = vi.fn();
    const setStatus = vi.fn();
    const login = vi.spyOn(api, "post").mockResolvedValue({
      user: { id: "admin-1", email: "admin@example.test", display_name: "Admin", role: "ADMIN" },
      csrf_token: "csrf-after-login",
    });
    render(
      <QueryClientProvider client={createQueryClient()}>
        <SessionContext.Provider value={{ user: null, status: "unauthenticated", setUser, setStatus }}>
          <MemoryRouter><LoginPage /></MemoryRouter>
        </SessionContext.Provider>
      </QueryClientProvider>,
    );

    await user.type(screen.getByLabelText("Email"), "admin@example.test");
    await user.type(screen.getByLabelText("Password"), "correct horse battery staple");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(login).toHaveBeenCalledWith("/auth/login", { email: "admin@example.test", password: "correct horse battery staple" });
    expect(setUser).toHaveBeenCalledWith(expect.objectContaining({ role: "ADMIN" }));
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });
});
