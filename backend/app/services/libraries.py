from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ControlDocument,
    ControlEvidence,
    Framework,
    FrameworkRequirement,
    FrameworkVersion,
    OrganizationalControl,
    RequirementAssessment,
    RequirementDocument,
    RequirementEvidence,
    StoredFile,
    User,
)


class LibraryNotFound(LookupError):
    pass


class LibraryValidationError(ValueError):
    pass


def validate_owner(session: Session, workspace_id: UUID, owner_id: UUID | None) -> None:
    if owner_id is None:
        return
    exists = session.scalar(
        select(User.id).where(User.id == owner_id, User.workspace_id == workspace_id)
    )
    if exists is None:
        raise LibraryValidationError("Library owner is outside this workspace.")


def owner_data(
    session: Session,
    workspace_id: UUID,
    owner_id: UUID | None,
) -> dict[str, object] | None:
    if owner_id is None:
        return None
    owner = session.scalar(
        select(User).where(User.id == owner_id, User.workspace_id == workspace_id)
    )
    if owner is None:
        return None
    return {
        "id": str(owner.id),
        "display_name": owner.display_name,
        "email": owner.email,
    }


def validate_requirements(
    session: Session,
    workspace_id: UUID,
    requirement_ids: Sequence[UUID],
) -> list[FrameworkRequirement]:
    unique_ids = set(requirement_ids)
    if not unique_ids:
        return []
    requirements = list(
        session.scalars(
            select(FrameworkRequirement)
            .join(
                RequirementAssessment,
                RequirementAssessment.requirement_id == FrameworkRequirement.id,
            )
            .where(
                FrameworkRequirement.id.in_(unique_ids),
                RequirementAssessment.workspace_id == workspace_id,
            )
        )
    )
    if len(requirements) != len(unique_ids):
        raise LibraryNotFound("One or more requirements were not found.")
    return requirements


def validate_controls(
    session: Session,
    workspace_id: UUID,
    control_ids: Sequence[UUID],
) -> list[OrganizationalControl]:
    unique_ids = set(control_ids)
    if not unique_ids:
        return []
    controls = list(
        session.scalars(
            select(OrganizationalControl).where(
                OrganizationalControl.workspace_id == workspace_id,
                OrganizationalControl.id.in_(unique_ids),
            )
        )
    )
    if len(controls) != len(unique_ids):
        raise LibraryNotFound("One or more controls were not found.")
    return controls


def file_data(file: StoredFile) -> dict[str, object]:
    return {
        "id": str(file.id),
        "original_filename": file.original_filename,
        "storage_key": file.storage_key,
        "extension": file.normalized_extension,
        "declared_media_type": file.declared_media_type,
        "detected_media_type": file.detected_media_type,
        "byte_size": file.byte_size,
        "sha256": file.sha256,
    }


def requirement_summaries_for_document(
    session: Session,
    workspace_id: UUID,
    document_id: UUID,
) -> list[dict[str, object]]:
    rows = session.execute(
        select(RequirementDocument, FrameworkRequirement, Framework, FrameworkVersion)
        .join(
            FrameworkRequirement,
            FrameworkRequirement.id == RequirementDocument.requirement_id,
        )
        .join(FrameworkVersion, FrameworkVersion.id == FrameworkRequirement.framework_version_id)
        .join(Framework, Framework.id == FrameworkVersion.framework_id)
        .where(
            RequirementDocument.workspace_id == workspace_id,
            RequirementDocument.document_id == document_id,
        )
        .order_by(Framework.name, FrameworkRequirement.sort_order)
    ).all()
    return [
        {
            "mapping_id": str(mapping.id),
            "id": str(requirement.id),
            "external_id": requirement.external_id,
            "title": requirement.title,
            "framework": framework.slug,
            "framework_version": version.version,
            "rationale": mapping.rationale,
        }
        for mapping, requirement, framework, version in rows
    ]


def requirement_summaries_for_evidence(
    session: Session,
    workspace_id: UUID,
    evidence_id: UUID,
) -> list[dict[str, object]]:
    rows = session.execute(
        select(RequirementEvidence, FrameworkRequirement, Framework, FrameworkVersion)
        .join(
            FrameworkRequirement,
            FrameworkRequirement.id == RequirementEvidence.requirement_id,
        )
        .join(FrameworkVersion, FrameworkVersion.id == FrameworkRequirement.framework_version_id)
        .join(Framework, Framework.id == FrameworkVersion.framework_id)
        .where(
            RequirementEvidence.workspace_id == workspace_id,
            RequirementEvidence.evidence_id == evidence_id,
        )
        .order_by(Framework.name, FrameworkRequirement.sort_order)
    ).all()
    return [
        {
            "mapping_id": str(mapping.id),
            "id": str(requirement.id),
            "external_id": requirement.external_id,
            "title": requirement.title,
            "framework": framework.slug,
            "framework_version": version.version,
            "rationale": mapping.rationale,
        }
        for mapping, requirement, framework, version in rows
    ]


def control_summaries_for_document(
    session: Session,
    workspace_id: UUID,
    document_id: UUID,
) -> list[dict[str, object]]:
    rows = session.execute(
        select(ControlDocument, OrganizationalControl)
        .join(OrganizationalControl, OrganizationalControl.id == ControlDocument.control_id)
        .where(
            ControlDocument.workspace_id == workspace_id,
            ControlDocument.document_id == document_id,
        )
        .order_by(OrganizationalControl.code)
    ).all()
    return [
        {
            "mapping_id": str(mapping.id),
            "id": str(control.id),
            "code": control.code,
            "name": control.name,
        }
        for mapping, control in rows
    ]


def control_summaries_for_evidence(
    session: Session,
    workspace_id: UUID,
    evidence_id: UUID,
) -> list[dict[str, object]]:
    rows = session.execute(
        select(ControlEvidence, OrganizationalControl)
        .join(OrganizationalControl, OrganizationalControl.id == ControlEvidence.control_id)
        .where(
            ControlEvidence.workspace_id == workspace_id,
            ControlEvidence.evidence_id == evidence_id,
        )
        .order_by(OrganizationalControl.code)
    ).all()
    return [
        {
            "mapping_id": str(mapping.id),
            "id": str(control.id),
            "code": control.code,
            "name": control.name,
        }
        for mapping, control in rows
    ]
