import type { RequirementSummary } from "../../app/api/types";

export function requirementFixture(
  overrides: Partial<RequirementSummary> = {},
): RequirementSummary {
  const externalId = overrides.external_id ?? "AC-1";
  return {
    id: `id-${externalId}`,
    external_id: externalId,
    title: "Account lifecycle",
    summary: "Approve, review, and remove access.",
    guidance: "Document the lifecycle and retain review evidence.",
    source_reference: "Internal framework",
    parent_id: null,
    framework: { id: "framework-custom", slug: "custom", name: "Custom framework", version: "1" },
    domain: { id: "domain-access", external_id: "ACCESS", name: "Access practice" },
    assessment: {
      id: `assessment-${externalId}`,
      status_code: "READY",
      applicability: "APPLICABLE",
      owner: null,
      assignee: null,
      due_date: null,
      implementation_notes: "Review runs quarterly.",
      tags: ["access"],
      revision: 1,
      updated_at: "2026-08-21T12:00:00Z",
    },
    document_count: 2,
    evidence_count: 4,
    control_count: 1,
    last_updated: "2026-08-21T12:00:00Z",
    ...overrides,
  };
}
