from collections.abc import Sequence
from datetime import date
from typing import BinaryIO
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ControlEvidence, Evidence, RequirementEvidence, StoredFile
from app.services.activity import record_activity
from app.services.libraries import (
    LibraryNotFound,
    control_summaries_for_evidence,
    file_data,
    owner_data,
    requirement_summaries_for_evidence,
    validate_controls,
    validate_owner,
    validate_requirements,
)
from app.services.uploads import store_upload
from app.storage import FileStorage


def create_evidence(
    session: Session,
    storage: FileStorage,
    *,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    name: str,
    description: str,
    evidence_date: date | None,
    owner_user_id: UUID | None,
    notes: str,
    requirement_ids: Sequence[UUID],
    control_ids: Sequence[UUID],
    filename: str,
    declared_media_type: str,
    stream: BinaryIO,
    limit: int,
    allowed_extensions: set[str],
) -> Evidence:
    requirements = validate_requirements(session, workspace_id, requirement_ids)
    controls = validate_controls(session, workspace_id, control_ids)
    validate_owner(session, workspace_id, owner_user_id)
    stored_file, created_file = store_upload(
        session,
        storage,
        workspace_id=workspace_id,
        uploaded_by_user_id=actor_user_id,
        filename=filename,
        declared_media_type=declared_media_type,
        stream=stream,
        limit=limit,
        allowed_extensions=allowed_extensions,
    )
    try:
        evidence = Evidence(
            workspace_id=workspace_id,
            stored_file_id=stored_file.id,
            name=name,
            description=description,
            evidence_date=evidence_date,
            owner_user_id=owner_user_id,
            notes=notes,
        )
        session.add(evidence)
        session.flush()
        for requirement in requirements:
            session.add(
                RequirementEvidence(
                    workspace_id=workspace_id,
                    requirement_id=requirement.id,
                    evidence_id=evidence.id,
                    rationale="",
                )
            )
            record_activity(
                session,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                entity_type="FRAMEWORK_REQUIREMENT",
                entity_id=requirement.id,
                action_code="EVIDENCE_MAPPED",
                before=None,
                after={"evidence_id": str(evidence.id), "name": evidence.name},
            )
        for control in controls:
            session.add(
                ControlEvidence(
                    workspace_id=workspace_id,
                    control_id=control.id,
                    evidence_id=evidence.id,
                )
            )
            record_activity(
                session,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                entity_type="ORGANIZATIONAL_CONTROL",
                entity_id=control.id,
                action_code="EVIDENCE_MAPPED",
                before=None,
                after={"evidence_id": str(evidence.id), "name": evidence.name},
            )
        session.flush()
        record_activity(
            session,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            entity_type="EVIDENCE",
            entity_id=evidence.id,
            action_code="EVIDENCE_UPLOADED",
            before=None,
            after={"name": evidence.name, "filename": stored_file.original_filename},
        )
        return evidence
    except Exception:
        if created_file:
            storage.delete(stored_file.storage_key)
        raise


def get_evidence(session: Session, workspace_id: UUID, evidence_id: UUID) -> Evidence:
    evidence = session.scalar(
        select(Evidence).where(Evidence.id == evidence_id, Evidence.workspace_id == workspace_id)
    )
    if evidence is None:
        raise LibraryNotFound("Evidence not found.")
    return evidence


def evidence_data(session: Session, evidence: Evidence) -> dict[str, object]:
    stored_file = session.scalar(
        select(StoredFile).where(
            StoredFile.id == evidence.stored_file_id,
            StoredFile.workspace_id == evidence.workspace_id,
        )
    )
    if stored_file is None:
        raise LibraryNotFound("Stored evidence file not found.")
    return {
        "id": str(evidence.id),
        "name": evidence.name,
        "description": evidence.description,
        "evidence_date": evidence.evidence_date.isoformat() if evidence.evidence_date else None,
        "owner_user_id": str(evidence.owner_user_id) if evidence.owner_user_id else None,
        "owner": owner_data(session, evidence.workspace_id, evidence.owner_user_id),
        "notes": evidence.notes,
        "revision": evidence.revision,
        "created_at": evidence.created_at.isoformat(),
        "updated_at": evidence.updated_at.isoformat(),
        "file": file_data(stored_file),
        "requirements": requirement_summaries_for_evidence(
            session, evidence.workspace_id, evidence.id
        ),
        "controls": control_summaries_for_evidence(session, evidence.workspace_id, evidence.id),
    }


def list_evidence(session: Session, workspace_id: UUID) -> list[dict[str, object]]:
    evidence = session.scalars(
        select(Evidence).where(Evidence.workspace_id == workspace_id).order_by(Evidence.name)
    ).all()
    return [evidence_data(session, item) for item in evidence]


def evidence_for_requirement(
    session: Session,
    workspace_id: UUID,
    requirement_id: UUID,
) -> list[dict[str, object]]:
    validate_requirements(session, workspace_id, [requirement_id])
    evidence = session.scalars(
        select(Evidence)
        .join(RequirementEvidence, RequirementEvidence.evidence_id == Evidence.id)
        .where(
            RequirementEvidence.workspace_id == workspace_id,
            RequirementEvidence.requirement_id == requirement_id,
        )
        .order_by(Evidence.name)
    ).all()
    return [evidence_data(session, item) for item in evidence]


def map_evidence_requirements(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    evidence_id: UUID,
    requirement_ids: Sequence[UUID],
    rationale: str,
) -> Evidence:
    evidence = get_evidence(session, workspace_id, evidence_id)
    requirements = validate_requirements(session, workspace_id, requirement_ids)
    existing = set(
        session.scalars(
            select(RequirementEvidence.requirement_id).where(
                RequirementEvidence.workspace_id == workspace_id,
                RequirementEvidence.evidence_id == evidence_id,
                RequirementEvidence.requirement_id.in_([item.id for item in requirements]),
            )
        )
    )
    for requirement in requirements:
        if requirement.id not in existing:
            session.add(
                RequirementEvidence(
                    workspace_id=workspace_id,
                    requirement_id=requirement.id,
                    evidence_id=evidence_id,
                    rationale=rationale,
                )
            )
            record_activity(
                session,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                entity_type="FRAMEWORK_REQUIREMENT",
                entity_id=requirement.id,
                action_code="EVIDENCE_MAPPED",
                before=None,
                after={"evidence_id": str(evidence_id), "name": evidence.name},
            )
    session.flush()
    return evidence


def map_evidence_controls(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    evidence_id: UUID,
    control_ids: Sequence[UUID],
) -> Evidence:
    evidence = get_evidence(session, workspace_id, evidence_id)
    controls = validate_controls(session, workspace_id, control_ids)
    existing = set(
        session.scalars(
            select(ControlEvidence.control_id).where(
                ControlEvidence.workspace_id == workspace_id,
                ControlEvidence.evidence_id == evidence_id,
                ControlEvidence.control_id.in_([item.id for item in controls]),
            )
        )
    )
    for control in controls:
        if control.id not in existing:
            session.add(
                ControlEvidence(
                    workspace_id=workspace_id,
                    control_id=control.id,
                    evidence_id=evidence_id,
                )
            )
            record_activity(
                session,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                entity_type="ORGANIZATIONAL_CONTROL",
                entity_id=control.id,
                action_code="EVIDENCE_MAPPED",
                before=None,
                after={"evidence_id": str(evidence.id), "name": evidence.name},
            )
    session.flush()
    return evidence


def evidence_for_control(
    session: Session,
    workspace_id: UUID,
    control_id: UUID,
) -> list[dict[str, object]]:
    validate_controls(session, workspace_id, [control_id])
    evidence = session.scalars(
        select(Evidence)
        .join(ControlEvidence, ControlEvidence.evidence_id == Evidence.id)
        .where(
            ControlEvidence.workspace_id == workspace_id,
            ControlEvidence.control_id == control_id,
        )
        .order_by(Evidence.name)
    ).all()
    return [evidence_data(session, item) for item in evidence]


def unmap_evidence_requirement(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    requirement_id: UUID,
    evidence_id: UUID,
) -> None:
    evidence = get_evidence(session, workspace_id, evidence_id)
    validate_requirements(session, workspace_id, [requirement_id])
    mapping = session.scalar(
        select(RequirementEvidence).where(
            RequirementEvidence.workspace_id == workspace_id,
            RequirementEvidence.requirement_id == requirement_id,
            RequirementEvidence.evidence_id == evidence_id,
        )
    )
    if mapping is None:
        return
    session.delete(mapping)
    record_activity(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="FRAMEWORK_REQUIREMENT",
        entity_id=requirement_id,
        action_code="EVIDENCE_UNMAPPED",
        before={
            "evidence_id": str(evidence.id),
            "name": evidence.name,
            "rationale": mapping.rationale,
        },
        after=None,
    )


def unmap_evidence_control(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    control_id: UUID,
    evidence_id: UUID,
) -> None:
    evidence = get_evidence(session, workspace_id, evidence_id)
    validate_controls(session, workspace_id, [control_id])
    mapping = session.scalar(
        select(ControlEvidence).where(
            ControlEvidence.workspace_id == workspace_id,
            ControlEvidence.control_id == control_id,
            ControlEvidence.evidence_id == evidence_id,
        )
    )
    if mapping is None:
        return
    session.delete(mapping)
    record_activity(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="ORGANIZATIONAL_CONTROL",
        entity_id=control_id,
        action_code="EVIDENCE_UNMAPPED",
        before={"evidence_id": str(evidence.id), "name": evidence.name},
        after=None,
    )
