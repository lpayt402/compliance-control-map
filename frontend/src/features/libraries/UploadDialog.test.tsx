import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../app/api/client";
import { createQueryClient } from "../../app/query-client";
import { requirementFixture } from "../framework-map/test-fixtures";
import { UploadDialog } from "./UploadDialog";

afterEach(() => vi.restoreAllMocks());

describe("UploadDialog", () => {
  it("uploads one document while mapping it to multiple requirements", async () => {
    const user = userEvent.setup();
    const upload = vi.spyOn(api, "upload").mockResolvedValue({ id: "document-1", name: "Access policy" });
    render(
      <QueryClientProvider client={createQueryClient()}>
        <UploadDialog
          kind="documents"
          onOpenChange={vi.fn()}
          open
          requirements={[
            requirementFixture(),
            requirementFixture({ id: "id-AC-2", external_id: "AC-2" }),
          ]}
        />
      </QueryClientProvider>,
    );

    expect(screen.getByText(/PDF, DOCX, XLSX, CSV, TXT, images, ZIP, and JSON/)).toBeVisible();
    await user.type(screen.getByLabelText("Name"), "Access policy");
    await user.upload(screen.getByLabelText("File"), new File(["demo"], "access.txt", { type: "text/plain" }));
    await user.click(screen.getByRole("checkbox", { name: /AC-1/ }));
    await user.click(screen.getByRole("checkbox", { name: /AC-2/ }));
    await user.click(screen.getByRole("button", { name: "Upload" }));

    await waitFor(() => expect(upload).toHaveBeenCalledOnce());
    const form = upload.mock.calls[0]?.[1];
    expect(form?.getAll("requirement_ids")).toEqual(["id-AC-1", "id-AC-2"]);
  });

  it("starts with the entity target selected and makes it visible", () => {
    const requirement = requirementFixture();
    render(
      <QueryClientProvider client={createQueryClient()}>
        <UploadDialog
          controls={[{ id: "control-1", code: "AC-01", name: "Access review" }]}
          initialControlIds={["control-1"]}
          initialRequirementIds={[requirement.id]}
          kind="evidence"
          onOpenChange={vi.fn()}
          open
          requirements={[requirement]}
        />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("checkbox", { name: /AC-1 Account lifecycle/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /AC-01 Access review/ })).toBeChecked();
    expect(screen.getByText("This upload will be attached to 2 selected targets.")).toBeVisible();
  });
});
