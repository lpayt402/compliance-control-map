import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../app/api/client";
import { createQueryClient } from "../../app/query-client";
import { requirementFixture } from "../framework-map/test-fixtures";
import { LibraryDetail } from "./LibraryDetail";
import type { LibraryRecord } from "./library-types";

afterEach(() => vi.restoreAllMocks());

describe("LibraryDetail", () => {
  it("links controls and detaches requirement mappings", async () => {
    const user = userEvent.setup();
    const record = {
      id: "document-1",
      name: "Access policy",
      description: "Approved policy",
      document_type: "POLICY",
      owner_user_id: null,
      notes: "",
      revision: 1,
      created_at: "2026-08-24T00:00:00Z",
      updated_at: "2026-08-24T00:00:00Z",
      file: { id: "file-1", original_filename: "access.txt", extension: ".txt", detected_media_type: "text/plain", byte_size: 10, sha256: "hidden" },
      requirements: [{ mapping_id: "mapping-1", id: "requirement-1", external_id: "AC-1", title: "Account lifecycle", framework: "custom", framework_version: "1", rationale: "" }],
      controls: [],
    } satisfies LibraryRecord;
    const post = vi.spyOn(api, "post").mockResolvedValue(record);
    const remove = vi.spyOn(api, "delete").mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(
      <QueryClientProvider client={createQueryClient()}>
        <LibraryDetail
          canEdit
          controls={[{ id: "control-1", code: "AC-01", name: "Access review" }]}
          kind="documents"
          record={record}
          requirements={[requirementFixture({ id: "requirement-2", external_id: "AC-2" })]}
        />
      </QueryClientProvider>,
    );

    await user.selectOptions(screen.getByLabelText("Add control mapping"), "control-1");
    await user.click(screen.getByRole("button", { name: "Map selected controls" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      "/documents/document-1/controls",
      { control_ids: ["control-1"] },
    ));
    await user.click(screen.getByRole("button", { name: "Detach AC-1" }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith(
      "/requirements/requirement-1/documents/document-1",
    ));
  });
});
