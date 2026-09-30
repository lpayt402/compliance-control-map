from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ControlNote,
    OrganizationalControl,
    RequirementAssessment,
    RequirementNote,
    User,
)
from app.services.activity import record_activity

TextResource = RequirementNote | ControlNote


class TextResourceNotFound(LookupError):
    pass


class TextResourceValidationError(ValueError):
    pass


class TextResourceConflict(RuntimeError):
    def __init__(self, current_revision: int) -> None:
        super().__init__("Resource changed before the update.")
        self.current_revision = current_revision


def _user_summary(user: User | None) -> dict[str, str] | None:
    if user is None:
        return None
    return {
        "id": str(user.id),
        "display_name": user.display_name,
        "email": user.email or "",
    }


def resource_data(session: Session, resource: TextResource) -> dict[str, object]:
    author = session.get(User, resource.author_user_id) if resource.author_user_id else None
    contact = session.get(User, resource.contact_user_id) if resource.contact_user_id else None
    return {
        "id": str(resource.id),
        "kind": resource.kind,
        "title": resource.title,
        "body": resource.body,
        "author_user_id": str(resource.author_user_id) if resource.author_user_id else None,
        "author": _user_summary(author),
        "contact_user_id": str(resource.contact_user_id) if resource.contact_user_id else None,
        "contact_user": _user_summary(contact),
        "revision": resource.revision,
        "created_at": resource.created_at.isoformat(),
        "edited_at": resource.edited_at.isoformat() if resource.edited_at else None,
    }


def _snapshot(resource: TextResource) -> dict[str, object]:
    return {
        "resource_id": str(resource.id),
        "kind": resource.kind,
        "title": resource.title,
        "body": resource.body,
        "contact_user_id": (
            str(resource.contact_user_id) if resource.contact_user_id else None
        ),
        "revision": resource.revision,
    }


def _validated_values(
    session: Session,
    workspace_id: UUID,
    values: dict[str, Any],
) -> dict[str, Any]:
    kind = str(values.get("kind", "NOTE"))
    title = str(values.get("title", "")).strip()
    body = str(values.get("body", ""))
    contact_user_id = values.get("contact_user_id")
    if kind not in {"NOTE", "PLAYBOOK", "CONTACT"}:
        raise TextResourceValidationError("Unknown resource kind.")
    if not body.strip():
        raise TextResourceValidationError("Resource text must contain visible characters.")
    if len(body) > 10_000 or len(title) > 240:
        raise TextResourceValidationError("Resource text is too long.")
    if kind != "NOTE" and not title:
        raise TextResourceValidationError("Playbooks and contacts require a title.")
    if kind != "CONTACT" and contact_user_id is not None:
        raise TextResourceValidationError(
            "Only contact resources can reference a workspace user."
        )
    if contact_user_id is not None:
        if not isinstance(contact_user_id, UUID):
            raise TextResourceValidationError("Invalid contact user.")
        user = session.scalar(
            select(User).where(
                User.id == contact_user_id,
                User.workspace_id == workspace_id,
                User.is_disabled.is_(False),
            )
        )
        if user is None:
            raise TextResourceNotFound("Contact user not found.")
    return {
        "kind": kind,
        "title": title,
        "body": body,
        "contact_user_id": contact_user_id,
    }


def _requirement_assessment(
    session: Session, workspace_id: UUID, requirement_id: UUID
) -> RequirementAssessment:
    assessment = session.scalar(
        select(RequirementAssessment).where(
            RequirementAssessment.workspace_id == workspace_id,
            RequirementAssessment.requirement_id == requirement_id,
        )
    )
    if assessment is None:
        raise TextResourceNotFound("Requirement not found.")
    return assessment


def _control(session: Session, workspace_id: UUID, control_id: UUID) -> OrganizationalControl:
    control = session.scalar(
        select(OrganizationalControl).where(
            OrganizationalControl.workspace_id == workspace_id,
            OrganizationalControl.id == control_id,
        )
    )
    if control is None:
        raise TextResourceNotFound("Control not found.")
    return control


def create_requirement_resource(
    session: Session,
    workspace_id: UUID,
    requirement_id: UUID,
    actor_user_id: UUID | None,
    values: dict[str, Any],
) -> RequirementNote:
    assessment = _requirement_assessment(session, workspace_id, requirement_id)
    cleaned = _validated_values(session, workspace_id, values)
    resource = RequirementNote(
        workspace_id=workspace_id,
        assessment_id=assessment.id,
        author_user_id=actor_user_id,
        **cleaned,
    )
    session.add(resource)
    session.flush()
    _record_resource_activity(
        session,
        resource,
        workspace_id,
        actor_user_id,
        "FRAMEWORK_REQUIREMENT",
        requirement_id,
        "CREATED",
        None,
    )
    return resource


def create_control_resource(
    session: Session,
    workspace_id: UUID,
    control_id: UUID,
    actor_user_id: UUID | None,
    values: dict[str, Any],
) -> ControlNote:
    _control(session, workspace_id, control_id)
    cleaned = _validated_values(session, workspace_id, values)
    resource = ControlNote(
        workspace_id=workspace_id,
        control_id=control_id,
        author_user_id=actor_user_id,
        **cleaned,
    )
    session.add(resource)
    session.flush()
    _record_resource_activity(
        session,
        resource,
        workspace_id,
        actor_user_id,
        "ORGANIZATIONAL_CONTROL",
        control_id,
        "CREATED",
        None,
    )
    return resource


def list_requirement_resources(
    session: Session, workspace_id: UUID, requirement_id: UUID
) -> list[RequirementNote]:
    assessment = _requirement_assessment(session, workspace_id, requirement_id)
    return list(
        session.scalars(
            select(RequirementNote)
            .where(
                RequirementNote.workspace_id == workspace_id,
                RequirementNote.assessment_id == assessment.id,
            )
            .order_by(RequirementNote.created_at.desc())
        )
    )


def list_control_resources(
    session: Session, workspace_id: UUID, control_id: UUID
) -> list[ControlNote]:
    _control(session, workspace_id, control_id)
    return list(
        session.scalars(
            select(ControlNote)
            .where(
                ControlNote.workspace_id == workspace_id,
                ControlNote.control_id == control_id,
            )
            .order_by(ControlNote.created_at.desc())
        )
    )


def _record_resource_activity(
    session: Session,
    resource: TextResource,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    entity_type: str,
    entity_id: UUID,
    verb: str,
    before: dict[str, object] | None,
) -> None:
    record_activity(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action_code=f"{resource.kind}_{verb}",
        before=before,
        after=None if verb == "DELETED" else _snapshot(resource),
    )


def _update_resource(
    session: Session,
    resource: TextResource,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    entity_type: str,
    entity_id: UUID,
    values: dict[str, Any],
    expected_revision: int,
) -> TextResource:
    if resource.revision != expected_revision:
        raise TextResourceConflict(resource.revision)
    before = _snapshot(resource)
    merged = {
        "kind": values.get("kind", resource.kind),
        "title": values.get("title", resource.title),
        "body": values.get("body", resource.body),
        "contact_user_id": values.get("contact_user_id", resource.contact_user_id),
    }
    cleaned = _validated_values(session, workspace_id, merged)
    for field, value in cleaned.items():
        setattr(resource, field, value)
    resource.revision += 1
    resource.edited_at = datetime.now(UTC)
    session.flush()
    _record_resource_activity(
        session,
        resource,
        workspace_id,
        actor_user_id,
        entity_type,
        entity_id,
        "UPDATED",
        before,
    )
    return resource


def update_requirement_resource(
    session: Session,
    workspace_id: UUID,
    requirement_id: UUID,
    resource_id: UUID,
    actor_user_id: UUID | None,
    values: dict[str, Any],
    expected_revision: int,
) -> RequirementNote:
    assessment = _requirement_assessment(session, workspace_id, requirement_id)
    resource = session.scalar(
        select(RequirementNote).where(
            RequirementNote.id == resource_id,
            RequirementNote.workspace_id == workspace_id,
            RequirementNote.assessment_id == assessment.id,
        )
    )
    if resource is None:
        raise TextResourceNotFound("Requirement resource not found.")
    return _update_resource(  # type: ignore[return-value]
        session,
        resource,
        workspace_id,
        actor_user_id,
        "FRAMEWORK_REQUIREMENT",
        requirement_id,
        values,
        expected_revision,
    )


def update_control_resource(
    session: Session,
    workspace_id: UUID,
    control_id: UUID,
    resource_id: UUID,
    actor_user_id: UUID | None,
    values: dict[str, Any],
    expected_revision: int,
) -> ControlNote:
    _control(session, workspace_id, control_id)
    resource = session.scalar(
        select(ControlNote).where(
            ControlNote.id == resource_id,
            ControlNote.workspace_id == workspace_id,
            ControlNote.control_id == control_id,
        )
    )
    if resource is None:
        raise TextResourceNotFound("Control resource not found.")
    return _update_resource(  # type: ignore[return-value]
        session,
        resource,
        workspace_id,
        actor_user_id,
        "ORGANIZATIONAL_CONTROL",
        control_id,
        values,
        expected_revision,
    )


def _delete_resource(
    session: Session,
    resource: TextResource,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    entity_type: str,
    entity_id: UUID,
    expected_revision: int,
) -> None:
    if resource.revision != expected_revision:
        raise TextResourceConflict(resource.revision)
    before = _snapshot(resource)
    _record_resource_activity(
        session,
        resource,
        workspace_id,
        actor_user_id,
        entity_type,
        entity_id,
        "DELETED",
        before,
    )
    session.delete(resource)


def delete_requirement_resource(
    session: Session,
    workspace_id: UUID,
    requirement_id: UUID,
    resource_id: UUID,
    actor_user_id: UUID | None,
    expected_revision: int,
) -> None:
    assessment = _requirement_assessment(session, workspace_id, requirement_id)
    resource = session.scalar(
        select(RequirementNote).where(
            RequirementNote.id == resource_id,
            RequirementNote.workspace_id == workspace_id,
            RequirementNote.assessment_id == assessment.id,
        )
    )
    if resource is None:
        raise TextResourceNotFound("Requirement resource not found.")
    _delete_resource(
        session,
        resource,
        workspace_id,
        actor_user_id,
        "FRAMEWORK_REQUIREMENT",
        requirement_id,
        expected_revision,
    )


def delete_control_resource(
    session: Session,
    workspace_id: UUID,
    control_id: UUID,
    resource_id: UUID,
    actor_user_id: UUID | None,
    expected_revision: int,
) -> None:
    _control(session, workspace_id, control_id)
    resource = session.scalar(
        select(ControlNote).where(
            ControlNote.id == resource_id,
            ControlNote.workspace_id == workspace_id,
            ControlNote.control_id == control_id,
        )
    )
    if resource is None:
        raise TextResourceNotFound("Control resource not found.")
    _delete_resource(
        session,
        resource,
        workspace_id,
        actor_user_id,
        "ORGANIZATIONAL_CONTROL",
        control_id,
        expected_revision,
    )
