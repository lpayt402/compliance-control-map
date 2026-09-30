import type { KeyboardEvent } from "react";

import type { RequirementSummary } from "../../app/api/types";
import { StatusMark } from "../../design/primitives/StatusMark";
import { statusLabels } from "../../design/primitives/status-labels";

function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

export function RequirementTile({
  active,
  onActivate,
  onKeyDown,
  requirement,
  buttonRef,
}: {
  active: boolean;
  onActivate: () => void;
  onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void;
  requirement: RequirementSummary;
  buttonRef?: (element: HTMLButtonElement | null) => void;
}) {
  const status = statusLabels[requirement.assessment.status_code];
  const accessibleName = [
    requirement.external_id,
    status,
    plural(requirement.document_count, "document"),
    plural(requirement.evidence_count, "evidence item", "evidence items"),
    plural(requirement.control_count, "control"),
  ].join(", ");

  return (
    <button
      aria-label={accessibleName}
      className={`requirement-tile requirement-tile--${requirement.assessment.status_code.toLowerCase()}`}
      data-requirement-id={requirement.external_id}
      onClick={onActivate}
      onKeyDown={onKeyDown}
      ref={buttonRef}
      tabIndex={active ? 0 : -1}
      type="button"
    >
      <span className="requirement-tile__rule" aria-hidden="true" />
      <span className="requirement-tile__identity">
        <strong>{requirement.external_id}</strong>
        <span>{requirement.title}</span>
      </span>
      <StatusMark status={requirement.assessment.status_code} compact />
      <span className="requirement-tile__counts" aria-hidden="true">
        <span>{requirement.document_count} doc</span>
        <span>{requirement.evidence_count} ev</span>
        <span>{requirement.control_count} ctrl</span>
      </span>
    </button>
  );
}
