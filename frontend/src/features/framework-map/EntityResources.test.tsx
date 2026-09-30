import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../app/api/client";
import { createQueryClient } from "../../app/query-client";
import { EntityResources } from "./EntityResources";

afterEach(() => vi.restoreAllMocks());

describe("EntityResources", () => {
  it("creates typed text resources and links existing documents from an entity", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "get").mockImplementation((path) => {
      if (path === "/documents") {
        return Promise.resolve([{ 
          id: "document-1",
          name: "Access policy",
          description: "Approved policy",
          file: { original_filename: "access.txt", byte_size: 12, detected_media_type: "text/plain" },
          requirements: [],
          controls: [],
        }] as never);
      }
      return Promise.resolve([] as never);
    });
    const post = vi.spyOn(api, "post").mockResolvedValue({ id: "created" });
    render(
      <QueryClientProvider client={createQueryClient()}>
        <EntityResources canEdit entityId="requirement-1" entityType="requirement" />
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Documents" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Evidence" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Notes, playbooks, and contacts" })).toBeVisible();

    await user.selectOptions(await screen.findByLabelText("Link existing document"), "document-1");
    await user.click(screen.getByRole("button", { name: "Link document" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      "/requirements/requirement-1/documents",
      { document_ids: ["document-1"], rationale: "" },
    ));

    await user.click(screen.getByRole("button", { name: "Add text resource" }));
    await user.selectOptions(screen.getByLabelText("Resource type"), "PLAYBOOK");
    await user.type(screen.getByLabelText("Title"), "Quarterly review");
    await user.type(screen.getByLabelText("Text"), "Collect approvals and retain the report.");
    await user.click(screen.getByRole("button", { name: "Save resource" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      "/requirements/requirement-1/notes",
      {
        kind: "PLAYBOOK",
        title: "Quarterly review",
        body: "Collect approvals and retain the report.",
        contact_user_id: null,
      },
    ));
  });

  it("keeps file and text metadata readable without Viewer mutation controls", async () => {
    vi.spyOn(api, "get").mockImplementation((path) => {
      if (path.endsWith("/documents")) return Promise.resolve([{
        id: "document-1",
        name: "Access policy",
        description: "Approved policy",
        document_type: "POLICY",
        effective_date: "2026-08-24",
        owner_user_id: "owner-1",
        owner: { id: "owner-1", display_name: "Policy Owner", email: null },
        updated_at: "2026-08-23T23:00:00Z",
        file: { original_filename: "access.txt", byte_size: 12, detected_media_type: "text/plain" },
      }] as never);
      if (path.endsWith("/notes")) return Promise.resolve([{
        id: "note-1", kind: "NOTE", title: "", body: "Read-only context.", revision: 1,
        author: null, contact_user: null, contact_user_id: null,
        created_at: "2026-08-24T00:00:00Z", edited_at: null,
      }] as never);
      return Promise.resolve([] as never);
    });
    render(
      <QueryClientProvider client={createQueryClient()}>
        <EntityResources canEdit={false} entityId="requirement-1" entityType="requirement" />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Access policy")).toBeVisible();
    expect(screen.getByText("Policy Owner")).toBeVisible();
    expect(screen.getByText(/Aug 24, 2026/)).toBeVisible();
    expect(screen.getByText("Read-only context.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Download" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Add text resource" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Detach" })).not.toBeInTheDocument();
  });
});
