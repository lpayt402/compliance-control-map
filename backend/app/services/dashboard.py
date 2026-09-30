from datetime import UTC, date, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ActivityEvent,
    ControlDocument,
    ControlEvidence,
    Framework,
    FrameworkDomain,
    FrameworkRequirement,
    FrameworkVersion,
    RequirementAssessment,
    RequirementControlMapping,
    RequirementDocument,
    RequirementEvidence,
)

STATUS_CODES = (
    "NOT_ASSESSED",
    "GAP",
    "IN_PROGRESS",
    "PARTIAL",
    "READY",
    "NOT_APPLICABLE",
)
DashboardRow = tuple[
    FrameworkRequirement,
    FrameworkDomain,
    Framework,
    FrameworkVersion,
    RequirementAssessment,
]


def _percentage(numerator: int, denominator: int) -> int:
    if denominator == 0:
        return 0
    return (numerator * 100 + denominator // 2) // denominator


def _requirement_rows(session: Session, workspace_id: UUID) -> list[DashboardRow]:
    return cast(
        list[DashboardRow],
        list(
        session.execute(
            select(
                FrameworkRequirement,
                FrameworkDomain,
                Framework,
                FrameworkVersion,
                RequirementAssessment,
            )
            .join(FrameworkDomain, FrameworkDomain.id == FrameworkRequirement.domain_id)
            .join(
                FrameworkVersion,
                FrameworkVersion.id == FrameworkRequirement.framework_version_id,
            )
            .join(Framework, Framework.id == FrameworkVersion.framework_id)
            .join(
                RequirementAssessment,
                RequirementAssessment.requirement_id == FrameworkRequirement.id,
            )
            .where(RequirementAssessment.workspace_id == workspace_id)
            .order_by(Framework.name, FrameworkDomain.sort_order, FrameworkRequirement.sort_order)
        )
        ),
    )


def _covered_requirement_ids(
    session: Session,
    workspace_id: UUID,
    *,
    kind: str,
) -> set[UUID]:
    if kind == "document":
        direct = set(
            session.scalars(
                select(RequirementDocument.requirement_id).where(
                    RequirementDocument.workspace_id == workspace_id
                )
            )
        )
        indirect = set(
            session.scalars(
                select(RequirementControlMapping.requirement_id)
                .join(
                    ControlDocument,
                    ControlDocument.control_id == RequirementControlMapping.control_id,
                )
                .where(
                    RequirementControlMapping.workspace_id == workspace_id,
                    ControlDocument.workspace_id == workspace_id,
                )
            )
        )
    else:
        direct = set(
            session.scalars(
                select(RequirementEvidence.requirement_id).where(
                    RequirementEvidence.workspace_id == workspace_id
                )
            )
        )
        indirect = set(
            session.scalars(
                select(RequirementControlMapping.requirement_id)
                .join(
                    ControlEvidence,
                    ControlEvidence.control_id == RequirementControlMapping.control_id,
                )
                .where(
                    RequirementControlMapping.workspace_id == workspace_id,
                    ControlEvidence.workspace_id == workspace_id,
                )
            )
        )
    return direct | indirect


def _queue_item(row: DashboardRow) -> dict[str, object]:
    requirement, domain, framework, version, assessment = row
    return {
        "id": str(requirement.id),
        "external_id": requirement.external_id,
        "title": requirement.title,
        "domain": domain.external_id,
        "framework": framework.slug,
        "framework_version": version.version,
        "status_code": assessment.status_code,
        "due_date": assessment.due_date.isoformat() if assessment.due_date else None,
        "updated_at": assessment.updated_at.isoformat(),
    }


def calculate_dashboard(session: Session, workspace_id: UUID) -> dict[str, object]:
    rows = _requirement_rows(session, workspace_id)
    counts = {status: 0 for status in STATUS_CODES}
    for row in rows:
        counts[row[4].status_code] = counts.get(row[4].status_code, 0) + 1
    denominator = len(rows) - counts["NOT_APPLICABLE"]
    assessed = denominator - counts["NOT_ASSESSED"]
    documented = _covered_requirement_ids(session, workspace_id, kind="document")
    evidenced = _covered_requirement_ids(session, workspace_id, kind="evidence")
    applicable_rows = [row for row in rows if row[4].status_code != "NOT_APPLICABLE"]
    missing_docs = [row for row in applicable_rows if row[0].id not in documented]
    missing_evidence = [row for row in applicable_rows if row[0].id not in evidenced]
    gaps = [row for row in applicable_rows if row[4].status_code == "GAP"]
    overdue = [
        row
        for row in applicable_rows
        if row[4].due_date is not None
        and row[4].due_date < date.today()
        and row[4].status_code != "READY"
    ]
    overdue.sort(key=lambda row: (row[4].due_date, row[0].external_id))
    gaps.sort(key=lambda row: row[0].external_id)

    recent_events = session.scalars(
        select(ActivityEvent)
        .where(
            ActivityEvent.workspace_id == workspace_id,
            ActivityEvent.entity_type == "FRAMEWORK_REQUIREMENT",
        )
        .order_by(ActivityEvent.created_at.desc())
        .limit(10)
    ).all()
    requirement_index = {row[0].id: row for row in rows}
    recent = [
        {
            **_queue_item(requirement_index[event.entity_id]),
            "action_code": event.action_code,
            "changed_at": event.created_at.isoformat(),
        }
        for event in recent_events
        if event.entity_id in requirement_index
    ]
    return {
        "counts": counts,
        "total_requirements": len(rows),
        "denominator": denominator,
        "ready_numerator": counts["READY"],
        "readiness_percentage": _percentage(counts["READY"], denominator),
        "assessed_numerator": assessed,
        "assessed_percentage": _percentage(assessed, denominator),
        "formula": "READY / (ALL - NOT_APPLICABLE)",
        "missing_documentation_count": len(missing_docs),
        "missing_evidence_count": len(missing_evidence),
        "missing_documentation": [_queue_item(row) for row in missing_docs[:10]],
        "missing_evidence": [_queue_item(row) for row in missing_evidence[:10]],
        "overdue": [_queue_item(row) for row in overdue[:10]],
        "gaps": [_queue_item(row) for row in gaps[:10]],
        "recently_changed": recent,
        "as_of": datetime.now(UTC).isoformat(),
    }
