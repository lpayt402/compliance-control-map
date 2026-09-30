import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../app/api/client";
import { createQueryClient } from "../../app/query-client";
import { FrameworkMapPage } from "./FrameworkMapPage";
import { requirementFixture } from "./test-fixtures";

function renderMap() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/frameworks/custom/map"]}>
        <Routes>
          <Route path="/frameworks/:framework/map" element={<FrameworkMapPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("FrameworkMapPage", () => {
  it("renders arbitrary framework data without SOC 2 assumptions", async () => {
    vi.spyOn(api, "get").mockResolvedValue([requirementFixture()]);

    renderMap();

    expect(
      await screen.findByRole("button", {
        name: "AC-1, Ready, 2 documents, 4 evidence items, 1 control",
      }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Access practice" })).toBeVisible();
    expect(screen.queryByText(/SOC 2/i)).not.toBeInTheDocument();
  });

  it("combines status and domain filters while updating the live count", async () => {
    const user = userEvent.setup();
    const gap = requirementFixture({
      id: "id-RISK-1",
      external_id: "RISK-1",
      domain: { id: "domain-risk", external_id: "RISK", name: "Risk practice" },
      assessment: { ...requirementFixture().assessment, id: "assessment-risk", status_code: "GAP" },
      document_count: 0,
      evidence_count: 0,
    });
    vi.spyOn(api, "get").mockResolvedValue([requirementFixture(), gap]);
    renderMap();
    await screen.findByRole("button", { name: /AC-1/ });

    await user.click(screen.getByRole("checkbox", { name: "Ready" }));
    await user.selectOptions(screen.getByLabelText("Domain"), "ACCESS");

    expect(screen.getByRole("status")).toHaveTextContent("1 requirement shown");
    expect(screen.getByRole("button", { name: /AC-1/ })).toBeVisible();
    expect(screen.queryByRole("button", { name: /RISK-1/ })).not.toBeInTheDocument();
  });

  it("moves the single tab stop with arrow keys", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "get").mockResolvedValue([
      requirementFixture(),
      requirementFixture({ id: "id-AC-2", external_id: "AC-2" }),
    ]);
    renderMap();
    const first = await screen.findByRole("button", { name: /AC-1/ });
    const second = screen.getByRole("button", { name: /AC-2/ });
    first.focus();

    await user.keyboard("{ArrowRight}");

    expect(second).toHaveFocus();
    expect(first).toHaveAttribute("tabindex", "-1");
    expect(second).toHaveAttribute("tabindex", "0");
  });
});
