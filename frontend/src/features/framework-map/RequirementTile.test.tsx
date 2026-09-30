import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RequirementTile } from "./RequirementTile";
import { requirementFixture } from "./test-fixtures";

describe("RequirementTile", () => {
  it("announces identifier, status, documents, and evidence without color dependence", () => {
    render(
      <RequirementTile
        active
        onActivate={vi.fn()}
        onKeyDown={vi.fn()}
        requirement={requirementFixture()}
      />,
    );

    expect(
      screen.getByRole("button", {
        name: "AC-1, Ready, 2 documents, 4 evidence items, 1 control",
      }),
    ).toBeVisible();
    expect(screen.getByText("Ready")).toBeVisible();
  });
});
