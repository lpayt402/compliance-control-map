import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "./app/api/client";
import { App } from "./App";

afterEach(() => vi.restoreAllMocks());

describe("App", () => {
  it("names the workspace", async () => {
    vi.spyOn(api, "get").mockImplementation((path) => path === "/auth/me"
      ? Promise.resolve({ id: null, email: null, display_name: "Local administrator", role: "ADMIN" })
      : new Promise(() => undefined));
    render(<App initialEntries={["/dashboard"]} />);
    expect(await screen.findByRole("heading", { name: "Compliance Control Map" })).toBeVisible();
  });
});
