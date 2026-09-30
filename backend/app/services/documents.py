from collections.abc import Sequence
from datetime import date
from typing import BinaryIO
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ControlDocument, Document, RequirementDocument, StoredFile
from app.services.activity import record_activity
from app.services.libraries import (
    LibraryNotFound,
    control_summaries_for_document,
    file_data,
    owner_data,
    requirement_summaries_for_document,
    validate_controls,
    validate_owner,
    validate_requirements,
)
from app.services.uploads import store_upload
from app.storage import FileStorage


def create_document(
    session: Session,
    storage: FileStorage,
    *,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    name: str,
    document_type: str,
    description: str,
    version: str,
    effective_date: date | None,
    owner_user_id: UUID | None,
    notes: str,
    requirement_ids: Sequence[UUID],
    control_ids: Sequence[UUID],
    filename: str,
    declared_media_type: str,
    stream: BinaryIO,
    limit: int,
    allowed_extensions: set[str],
) -> Document:
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
        document = Document(
            workspace_id=workspace_id,
            stored_file_id=stored_file.id,
            name=name,
            document_type=document_type,
            description=description,
            version=version,
            effective_date=effective_date,
            owner_user_id=owner_user_id,
            notes=notes,
        )
        session.add(document)
        session.flush()
        for requirement in requirements:
            session.add(
                RequirementDocument(
                    workspace_id=workspace_id,
                    requirement_id=requirement.id,
                    document_id=document.id,
                    rationale="",
                )
            )
            record_activity(
                session,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                entity_type="FRAMEWORK_REQUIREMENT",
                entity_id=requirement.id,
                action_code="DOCUMENT_MAPPED",
                before=None,
                after={"document_id": str(document.id), "name": document.name},
            )
        for control in controls:
            session.add(
                ControlDocument(
                    workspace_id=workspace_id,
                    control_id=control.id,
                    document_id=document.id,
                )
            )
            record_activity(
                session,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                entity_type="ORGANIZATIONAL_CONTROL",
                entity_id=control.id,
                action_code="DOCUMENT_MAPPED",
                before=None,
                after={"document_id": str(document.id), "name": document.name},
            )
        session.flush()
        record_activity(
            session,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            entity_type="DOCUMENT",
            entity_id=document.id,
            action_code="DOCUMENT_UPLOADED",
            before=None,
            after={"name": document.name, "filename": stored_file.original_filename},
        )
        return document
    except Exception:
        if created_file:
            storage.delete(stored_file.storage_key)
        raise


def get_document(session: Session, workspace_id: UUID, document_id: UUID) -> Document:
    document = session.scalar(
        select(Document).where(Document.id == document_id, Document.workspace_id == workspace_id)
    )
    if document is None:
        raise LibraryNotFound("Document not found.")
    return document


def document_data(session: Session, document: Document) -> dict[str, object]:
    stored_file = session.scalar(
        select(StoredFile).where(
            StoredFile.id == document.stored_file_id,
            StoredFile.workspace_id == document.workspace_id,
        )
    )
    if stored_file is None:
        raise LibraryNotFound("Stored document file not found.")
    return {
        "id": str(document.id),
        "name": document.name,
        "document_type": document.document_type,
        "description": document.description,
        "version": document.version,
        "effective_date": document.effective_date.isoformat() if document.effective_date else None,
        "owner_user_id": str(document.owner_user_id) if document.owner_user_id else None,
        "owner": owner_data(session, document.workspace_id, document.owner_user_id),
        "notes": document.notes,
        "revision": document.revision,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
        "file": file_data(stored_file),
        "requirements": requirement_summaries_for_document(
            session, document.workspace_id, document.id
        ),
        "controls": control_summaries_for_document(session, document.workspace_id, document.id),
    }


def list_documents(session: Session, workspace_id: UUID) -> list[dict[str, object]]:
    documents = session.scalars(
        select(Document).where(Document.workspace_id == workspace_id).order_by(Document.name)
    ).all()
    return [document_data(session, document) for document in documents]


def map_document_requirements(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    document_id: UUID,
    requirement_ids: Sequence[UUID],
    rationale: str,
) -> Document:
    document = get_document(session, workspace_id, document_id)
    requirements = validate_requirements(session, workspace_id, requirement_ids)
    existing = set(
        session.scalars(
            select(RequirementDocument.requirement_id).where(
                RequirementDocument.workspace_id == workspace_id,
                RequirementDocument.document_id == document_id,
                RequirementDocument.requirement_id.in_([item.id for item in requirements]),
            )
        )
    )
    for requirement in requirements:
        if requirement.id not in existing:
            session.add(
                RequirementDocument(
                    workspace_id=workspace_id,
                    requirement_id=requirement.id,
                    document_id=document_id,
                    rationale=rationale,
                )
            )
            record_activity(
                session,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                entity_type="FRAMEWORK_REQUIREMENT",
                entity_id=requirement.id,
                action_code="DOCUMENT_MAPPED",
                before=None,
                after={"document_id": str(document_id), "name": document.name},
            )
    session.flush()
    return document


def documents_for_requirement(
    session: Session,
    workspace_id: UUID,
    requirement_id: UUID,
) -> list[dict[str, object]]:
    validate_requirements(session, workspace_id, [requirement_id])
    documents = session.scalars(
        select(Document)
        .join(RequirementDocument, RequirementDocument.document_id == Document.id)
        .where(
            RequirementDocument.workspace_id == workspace_id,
            RequirementDocument.requirement_id == requirement_id,
        )
        .order_by(Document.name)
    ).all()
    return [document_data(session, document) for document in documents]


def map_document_controls(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    document_id: UUID,
    control_ids: Sequence[UUID],
) -> Document:
    document = get_document(session, workspace_id, document_id)
    controls = validate_controls(session, workspace_id, control_ids)
    existing = set(
        session.scalars(
            select(ControlDocument.control_id).where(
                ControlDocument.workspace_id == workspace_id,
                ControlDocument.document_id == document_id,
                ControlDocument.control_id.in_([item.id for item in controls]),
            )
        )
    )
    for control in controls:
        if control.id not in existing:
            session.add(
                ControlDocument(
                    workspace_id=workspace_id,
                    control_id=control.id,
                    document_id=document_id,
                )
            )
            record_activity(
                session,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                entity_type="ORGANIZATIONAL_CONTROL",
                entity_id=control.id,
                action_code="DOCUMENT_MAPPED",
                before=None,
                after={"document_id": str(document.id), "name": document.name},
            )
    session.flush()
    return document


def documents_for_control(
    session: Session,
    workspace_id: UUID,
    control_id: UUID,
) -> list[dict[str, object]]:
    validate_controls(session, workspace_id, [control_id])
    documents = session.scalars(
        select(Document)
        .join(ControlDocument, ControlDocument.document_id == Document.id)
        .where(
            ControlDocument.workspace_id == workspace_id,
            ControlDocument.control_id == control_id,
        )
        .order_by(Document.name)
    ).all()
    return [document_data(session, document) for document in documents]


def unmap_document_requirement(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    requirement_id: UUID,
    document_id: UUID,
) -> None:
    document = get_document(session, workspace_id, document_id)
    validate_requirements(session, workspace_id, [requirement_id])
    mapping = session.scalar(
        select(RequirementDocument).where(
            RequirementDocument.workspace_id == workspace_id,
            RequirementDocument.requirement_id == requirement_id,
            RequirementDocument.document_id == document_id,
        )
    )
    if mapping is None:
        return
    before: dict[str, object] = {
        "document_id": str(document.id),
        "name": document.name,
        "rationale": mapping.rationale,
    }
    session.delete(mapping)
    record_activity(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="FRAMEWORK_REQUIREMENT",
        entity_id=requirement_id,
        action_code="DOCUMENT_UNMAPPED",
        before=before,
        after=None,
    )


def unmap_document_control(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    control_id: UUID,
    document_id: UUID,
) -> None:
    document = get_document(session, workspace_id, document_id)
    validate_controls(session, workspace_id, [control_id])
    mapping = session.scalar(
        select(ControlDocument).where(
            ControlDocument.workspace_id == workspace_id,
            ControlDocument.control_id == control_id,
            ControlDocument.document_id == document_id,
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
        action_code="DOCUMENT_UNMAPPED",
        before={"document_id": str(document.id), "name": document.name},
        after=None,
    )
