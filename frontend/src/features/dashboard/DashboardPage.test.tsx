import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../app/api/client";
import { createQueryClient } from "../../app/query-client";
import { DashboardPage } from "./DashboardPage";

afterEach(() => vi.restoreAllMocks());

describe("DashboardPage", () => {
  it("explains readiness instead of implying fractional precision", async () => {
    vi.spyOn(api, "get").mockResolvedValue({
      counts: { NOT_ASSESSED: 0, GAP: 1, IN_PROGRESS: 0, PARTIAL: 1, READY: 1, NOT_APPLICABLE: 1 },
      total_requirements: 4,
      denominator: 3,
      ready_numerator: 1,
      readiness_percentage: 33,
      assessed_numerator: 3,
      assessed_percentage: 100,
      formula: "READY / (ALL - NOT_APPLICABLE)",
      missing_documentation_count: 1,
      missing_evidence_count: 2,
      missing_documentation: [],
      missing_evidence: [],
      overdue: [],
      gaps: [],
      recently_changed: [],
      as_of: "2026-08-21T12:00:00Z",
    });
    render(
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter><DashboardPage /></MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("33% ready")).toBeVisible();
    expect(screen.getByText("1 Ready ÷ 3 applicable requirements")).toBeVisible();
    expect(screen.getByText("100% assessed")).toBeVisible();
    expect(screen.getByText("Not applicable is excluded from readiness.")).toBeVisible();
  });
});
