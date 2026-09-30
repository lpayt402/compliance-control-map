import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../app/api/client";
import { createQueryClient } from "../../app/query-client";
import { requirementFixture } from "../framework-map/test-fixtures";
import { AssessmentTable } from "./AssessmentTable";

afterEach(() => vi.restoreAllMocks());

describe("AssessmentTable", () => {
  it("uses a native sortable table and saves inline readiness", async () => {
    const user = userEvent.setup();
    const first = requirementFixture({ title: "Zebra access", external_id: "AC-1" });
    const second = requirementFixture({ id: "id-AC-2", title: "Account review", external_id: "AC-2" });
    const patch = vi.spyOn(api, "patch").mockResolvedValue({
      ...first,
      assessment: { ...first.assessment, status_code: "PARTIAL", revision: 2 },
    });
    render(
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter><AssessmentTable requirements={[first, second]} canEdit /></MemoryRouter>
      </QueryClientProvider>,
    );

    const table = screen.getByRole("table", { name: "Requirement assessment tracker" });
    expect(within(table).getByRole("columnheader", { name: /Identifier/ })).toHaveAttribute("aria-sort", "ascending");
    await user.click(within(table).getByRole("button", { name: "Sort by title" }));
    expect(within(table).getAllByRole("row")[1]!).toHaveTextContent("Account review");
    await user.selectOptions(screen.getAllByLabelText(/Readiness for/)[0]!, "PARTIAL");
    expect(patch).toHaveBeenCalledWith("/requirements/id-AC-2/assessment", expect.objectContaining({ status_code: "PARTIAL" }));
  });

  it("shows status as text when the viewer cannot edit", () => {
    render(<MemoryRouter><AssessmentTable requirements={[requirementFixture()]} canEdit={false} /></MemoryRouter>);
    expect(screen.queryByLabelText(/Readiness for/)).not.toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeVisible();
  });
});
