from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ControlTag,
    Framework,
    FrameworkDomain,
    FrameworkRequirement,
    FrameworkVersion,
    OrganizationalControl,
    RequirementAssessment,
    RequirementControlMapping,
    StatusDefinition,
    Tag,
    User,
)
from app.services.activity import record_activity


class ControlNotFound(LookupError):
    pass


class ControlConflict(RuntimeError):
    def __init__(self, detail: str, current_revision: int | None = None) -> None:
        super().__init__(detail)
        self.current_revision = current_revision


class ControlValidationError(ValueError):
    pass


def _validate_status(session: Session, workspace_id: UUID, status_code: str) -> None:
    exists = session.scalar(
        select(StatusDefinition.id).where(
            StatusDefinition.workspace_id == workspace_id,
            StatusDefinition.scope == "CONTROL",
            StatusDefinition.code == status_code,
        )
    )
    if exists is None:
        raise ControlValidationError("Unknown control status.")


def _validate_owner(session: Session, workspace_id: UUID, owner_id: UUID | None) -> None:
    if owner_id is None:
        return
    exists = session.scalar(
        select(User.id).where(User.id == owner_id, User.workspace_id == workspace_id)
    )
    if exists is None:
        raise ControlValidationError("Control owner is outside this workspace.")


def _tags(session: Session, control_id: UUID) -> list[str]:
    return list(
        session.scalars(
            select(Tag.name)
            .join(ControlTag, ControlTag.tag_id == Tag.id)
            .where(ControlTag.control_id == control_id)
            .order_by(Tag.name)
        )
    )


def _replace_tags(
    session: Session,
    workspace_id: UUID,
    control_id: UUID,
    names: list[str],
) -> None:
    normalized = sorted({name.strip().casefold() for name in names if name.strip()})
    session.query(ControlTag).filter(ControlTag.control_id == control_id).delete(
        synchronize_session=False
    )
    for name in normalized:
        tag = session.scalar(
            select(Tag).where(Tag.workspace_id == workspace_id, Tag.name == name)
        )
        if tag is None:
            tag = Tag(workspace_id=workspace_id, name=name)
            session.add(tag)
            session.flush()
        session.add(
            ControlTag(workspace_id=workspace_id, control_id=control_id, tag_id=tag.id)
        )
    session.flush()


def _snapshot(session: Session, control: OrganizationalControl) -> dict[str, object]:
    return {
        "code": control.code,
        "name": control.name,
        "description": control.description,
        "status_code": control.status_code,
        "owner_user_id": str(control.owner_user_id) if control.owner_user_id else None,
        "implementation_notes": control.implementation_notes,
        "tags": _tags(session, control.id),
        "revision": control.revision,
    }


def create_control(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    values: dict[str, object],
) -> OrganizationalControl:
    code = str(values["code"]).strip()
    duplicate = session.scalar(
        select(OrganizationalControl.id).where(
            OrganizationalControl.workspace_id == workspace_id,
            OrganizationalControl.code == code,
        )
    )
    if duplicate is not None:
        raise ControlConflict("A control with that code already exists.")
    status_code = str(values.get("status_code", "PLANNED"))
    owner_id = values.get("owner_user_id")
    if owner_id is not None and not isinstance(owner_id, UUID):
        raise ControlValidationError("Invalid control owner.")
    _validate_status(session, workspace_id, status_code)
    _validate_owner(session, workspace_id, owner_id)
    control = OrganizationalControl(
        workspace_id=workspace_id,
        code=code,
        name=str(values["name"]).strip(),
        description=str(values.get("description", "")),
        status_code=status_code,
        owner_user_id=owner_id,
        implementation_notes=str(values.get("implementation_notes", "")),
    )
    session.add(control)
    session.flush()
    tags = values.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ControlValidationError("Invalid control tags.")
    _replace_tags(session, workspace_id, control.id, tags)
    record_activity(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="ORGANIZATIONAL_CONTROL",
        entity_id=control.id,
        action_code="CONTROL_CREATED",
        before=None,
        after=_snapshot(session, control),
    )
    return control


def update_control(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    control_id: UUID,
    values: dict[str, object],
    expected_revision: int,
) -> OrganizationalControl:
    control = session.scalar(
        select(OrganizationalControl).where(
            OrganizationalControl.id == control_id,
            OrganizationalControl.workspace_id == workspace_id,
        )
    )
    if control is None:
        raise ControlNotFound("Control not found.")
    if control.revision != expected_revision:
        raise ControlConflict("Control changed before the update.", control.revision)
    before = _snapshot(session, control)
    if "code" in values:
        code = str(values["code"]).strip()
        duplicate = session.scalar(
            select(OrganizationalControl.id).where(
                OrganizationalControl.workspace_id == workspace_id,
                OrganizationalControl.code == code,
                OrganizationalControl.id != control_id,
            )
        )
        if duplicate is not None:
            raise ControlConflict("A control with that code already exists.")
        control.code = code
    if "name" in values:
        control.name = str(values["name"]).strip()
    if "description" in values:
        control.description = str(values["description"])
    if "status_code" in values:
        status_code = str(values["status_code"])
        _validate_status(session, workspace_id, status_code)
        control.status_code = status_code
    if "owner_user_id" in values:
        owner_id = values["owner_user_id"]
        if owner_id is not None and not isinstance(owner_id, UUID):
            raise ControlValidationError("Invalid control owner.")
        _validate_owner(session, workspace_id, owner_id)
        control.owner_user_id = owner_id
    if "implementation_notes" in values:
        control.implementation_notes = str(values["implementation_notes"])
    if "tags" in values:
        tags = values["tags"]
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ControlValidationError("Invalid control tags.")
        _replace_tags(session, workspace_id, control.id, tags)
    control.revision += 1
    control.updated_at = datetime.now(UTC)
    session.flush()
    record_activity(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="ORGANIZATIONAL_CONTROL",
        entity_id=control.id,
        action_code="CONTROL_UPDATED",
        before=before,
        after=_snapshot(session, control),
    )
    return control


def _requirement_mappings(
    session: Session,
    workspace_id: UUID,
    control_id: UUID,
) -> list[dict[str, object]]:
    rows = session.execute(
        select(
            RequirementControlMapping,
            FrameworkRequirement,
            FrameworkDomain,
            Framework,
        )
        .join(
            FrameworkRequirement,
            FrameworkRequirement.id == RequirementControlMapping.requirement_id,
        )
        .join(FrameworkDomain, FrameworkDomain.id == FrameworkRequirement.domain_id)
        .join(FrameworkVersion, FrameworkVersion.id == FrameworkRequirement.framework_version_id)
        .join(Framework, Framework.id == FrameworkVersion.framework_id)
        .where(
            RequirementControlMapping.workspace_id == workspace_id,
            RequirementControlMapping.control_id == control_id,
        )
        .order_by(Framework.name, FrameworkRequirement.sort_order)
    ).all()
    return [
        {
            "id": str(mapping.id),
            "coverage": mapping.coverage,
            "rationale": mapping.rationale,
            "requirement": {
                "id": str(requirement.id),
                "external_id": requirement.external_id,
                "title": requirement.title,
                "domain": domain.external_id,
                "framework": framework.slug,
            },
        }
        for mapping, requirement, domain, framework in rows
    ]


def control_data(
    session: Session,
    control: OrganizationalControl,
    *,
    include_requirements: bool = True,
) -> dict[str, object]:
    owner = session.get(User, control.owner_user_id) if control.owner_user_id else None
    return {
        "id": str(control.id),
        "code": control.code,
        "name": control.name,
        "description": control.description,
        "status_code": control.status_code,
        "owner": (
            {"id": str(owner.id), "display_name": owner.display_name, "email": owner.email}
            if owner
            else None
        ),
        "implementation_notes": control.implementation_notes,
        "tags": _tags(session, control.id),
        "revision": control.revision,
        "created_at": control.created_at.isoformat(),
        "updated_at": control.updated_at.isoformat(),
        "requirements": (
            _requirement_mappings(session, control.workspace_id, control.id)
            if include_requirements
            else []
        ),
    }


def list_controls(session: Session, workspace_id: UUID) -> list[dict[str, object]]:
    controls = session.scalars(
        select(OrganizationalControl)
        .where(OrganizationalControl.workspace_id == workspace_id)
        .order_by(OrganizationalControl.code)
    ).all()
    return [control_data(session, control) for control in controls]


def get_control(
    session: Session,
    workspace_id: UUID,
    control_id: UUID,
) -> OrganizationalControl:
    control = session.scalar(
        select(OrganizationalControl).where(
            OrganizationalControl.id == control_id,
            OrganizationalControl.workspace_id == workspace_id,
        )
    )
    if control is None:
        raise ControlNotFound("Control not found.")
    return control


def link_control(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    requirement_id: UUID,
    control_id: UUID,
    coverage: str,
    rationale: str,
) -> RequirementControlMapping:
    requirement = session.scalar(
        select(FrameworkRequirement)
        .join(
            RequirementAssessment,
            RequirementAssessment.requirement_id == FrameworkRequirement.id,
        )
        .where(
            FrameworkRequirement.id == requirement_id,
            RequirementAssessment.workspace_id == workspace_id,
        )
    )
    control = session.scalar(
        select(OrganizationalControl).where(
            OrganizationalControl.id == control_id,
            OrganizationalControl.workspace_id == workspace_id,
        )
    )
    if requirement is None or control is None:
        raise ControlNotFound("Requirement or control not found.")
    duplicate = session.scalar(
        select(RequirementControlMapping.id).where(
            RequirementControlMapping.workspace_id == workspace_id,
            RequirementControlMapping.requirement_id == requirement_id,
            RequirementControlMapping.control_id == control_id,
        )
    )
    if duplicate is not None:
        raise ControlConflict("This control is already mapped to the requirement.")
    mapping = RequirementControlMapping(
        workspace_id=workspace_id,
        requirement_id=requirement_id,
        control_id=control_id,
        coverage=coverage,
        rationale=rationale,
    )
    session.add(mapping)
    session.flush()
    record_activity(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="FRAMEWORK_REQUIREMENT",
        entity_id=requirement_id,
        action_code="CONTROL_MAPPED",
        before=None,
        after={
            "control_id": str(control_id),
            "coverage": coverage,
            "rationale": rationale,
        },
    )
    return mapping


def unlink_control(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    requirement_id: UUID,
    control_id: UUID,
) -> None:
    mapping = session.scalar(
        select(RequirementControlMapping).where(
            RequirementControlMapping.workspace_id == workspace_id,
            RequirementControlMapping.requirement_id == requirement_id,
            RequirementControlMapping.control_id == control_id,
        )
    )
    if mapping is None:
        raise ControlNotFound("Control mapping not found.")
    before: dict[str, object] = {
        "control_id": str(control_id),
        "coverage": mapping.coverage,
        "rationale": mapping.rationale,
    }
    session.delete(mapping)
    record_activity(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="FRAMEWORK_REQUIREMENT",
        entity_id=requirement_id,
        action_code="CONTROL_UNMAPPED",
        before=before,
        after=None,
    )


def list_requirement_controls(
    session: Session,
    workspace_id: UUID,
    requirement_id: UUID,
) -> list[dict[str, object]]:
    rows = session.execute(
        select(RequirementControlMapping, OrganizationalControl)
        .join(
            OrganizationalControl,
            OrganizationalControl.id == RequirementControlMapping.control_id,
        )
        .where(
            RequirementControlMapping.workspace_id == workspace_id,
            RequirementControlMapping.requirement_id == requirement_id,
        )
        .order_by(OrganizationalControl.code)
    ).all()
    return [
        {
            "id": str(mapping.id),
            "coverage": mapping.coverage,
            "rationale": mapping.rationale,
            "control": control_data(session, control, include_requirements=False),
        }
        for mapping, control in rows
    ]
