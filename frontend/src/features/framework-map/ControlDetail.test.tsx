import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../app/api/client";
import { createQueryClient } from "../../app/query-client";
import { ControlDetail } from "./ControlDetail";

afterEach(() => vi.restoreAllMocks());

describe("ControlDetail", () => {
  it("edits a complete control and can remove its requirement mapping", async () => {
    const user = userEvent.setup();
    const control = {
      id: "control-1",
      code: "AC-01",
      name: "Access review",
      description: "Review access quarterly.",
      status_code: "OPERATING",
      owner: null,
      implementation_notes: "Security owns the review.",
      tags: ["access"],
      revision: 1,
      created_at: "2026-08-24T00:00:00Z",
      updated_at: "2026-08-24T00:00:00Z",
      requirements: [],
    };
    vi.spyOn(api, "get").mockImplementation((path) => Promise.resolve((
      path === "/controls/control-1" ? control : []
    ) as never));
    const patch = vi.spyOn(api, "patch").mockResolvedValue({ ...control, name: "Monthly access review", revision: 2 });
    const remove = vi.spyOn(api, "delete").mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(
      <QueryClientProvider client={createQueryClient()}>
        <ControlDetail
          canEdit
          controlId="control-1"
          onBack={vi.fn()}
          requirementId="requirement-1"
        />
      </QueryClientProvider>,
    );

    await user.clear(await screen.findByLabelText("Control name"));
    await user.type(screen.getByLabelText("Control name"), "Monthly access review");
    await user.click(screen.getByRole("button", { name: "Save control changes" }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith(
      "/controls/control-1",
      expect.objectContaining({ name: "Monthly access review", revision: 1 }),
    ));

    await user.click(screen.getByRole("button", { name: "Remove from requirement" }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith(
      "/requirements/requirement-1/controls/control-1",
    ));
  });
});
