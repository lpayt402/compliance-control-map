from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from app.models import (
    Framework,
    FrameworkRequirement,
    FrameworkVersion,
    RequirementAssessment,
    RequirementMapping,
)
from app.services.activity import record_activity


class CrosswalkNotFound(LookupError):
    pass


class CrosswalkConflict(RuntimeError):
    pass


def _available_requirement(
    session: Session,
    workspace_id: UUID,
    requirement_id: UUID,
) -> FrameworkRequirement | None:
    return session.scalar(
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


def create_mapping(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    *,
    source_requirement_id: UUID,
    target_requirement_id: UUID,
    relationship_type: str,
    confidence: int | None,
    mapping_source: str,
    notes: str,
) -> RequirementMapping:
    source = _available_requirement(session, workspace_id, source_requirement_id)
    target = _available_requirement(session, workspace_id, target_requirement_id)
    if source is None or target is None:
        raise CrosswalkNotFound("Source or target requirement not found.")
    duplicate = session.scalar(
        select(RequirementMapping.id).where(
            RequirementMapping.source_requirement_id == source_requirement_id,
            RequirementMapping.target_requirement_id == target_requirement_id,
            RequirementMapping.relationship_type == relationship_type,
            or_(
                RequirementMapping.workspace_id == workspace_id,
                RequirementMapping.workspace_id.is_(None),
            ),
        )
    )
    if duplicate is not None:
        raise CrosswalkConflict("That directed requirement mapping already exists.")
    mapping = RequirementMapping(
        workspace_id=workspace_id,
        source_requirement_id=source_requirement_id,
        target_requirement_id=target_requirement_id,
        relationship_type=relationship_type,
        confidence=confidence,
        mapping_source=mapping_source,
        notes=notes,
        created_by_user_id=actor_user_id,
    )
    session.add(mapping)
    session.flush()
    record_activity(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="FRAMEWORK_REQUIREMENT",
        entity_id=source_requirement_id,
        action_code="CROSSWALK_CREATED",
        before=None,
        after={
            "mapping_id": str(mapping.id),
            "target_requirement_id": str(target_requirement_id),
            "relationship_type": relationship_type,
            "confidence": confidence,
            "mapping_source": mapping_source,
        },
    )
    return mapping


def _requirement_summary(
    requirement: FrameworkRequirement,
    framework: Framework,
    version: FrameworkVersion,
) -> dict[str, object]:
    return {
        "id": str(requirement.id),
        "external_id": requirement.external_id,
        "title": requirement.title,
        "framework": {
            "slug": framework.slug,
            "name": framework.name,
            "version": version.version,
        },
    }


def mapping_data(
    session: Session,
    mapping: RequirementMapping,
    perspective_requirement_id: UUID | None = None,
) -> dict[str, object]:
    source_framework = aliased(Framework)
    target_framework = aliased(Framework)
    source_version = aliased(FrameworkVersion)
    target_version = aliased(FrameworkVersion)
    source_requirement = aliased(FrameworkRequirement)
    target_requirement = aliased(FrameworkRequirement)
    row = session.execute(
        select(
            source_requirement,
            source_framework,
            source_version,
            target_requirement,
            target_framework,
            target_version,
        )
        .join(source_version, source_version.id == source_requirement.framework_version_id)
        .join(source_framework, source_framework.id == source_version.framework_id)
        .join(target_requirement, target_requirement.id == mapping.target_requirement_id)
        .join(target_version, target_version.id == target_requirement.framework_version_id)
        .join(target_framework, target_framework.id == target_version.framework_id)
        .where(source_requirement.id == mapping.source_requirement_id)
    ).one()
    source, source_fw, source_ver, target, target_fw, target_ver = row
    direction = None
    other = None
    if perspective_requirement_id is not None:
        if perspective_requirement_id == mapping.source_requirement_id:
            direction = "OUTBOUND"
            other = _requirement_summary(target, target_fw, target_ver)
        else:
            direction = "INBOUND"
            other = _requirement_summary(source, source_fw, source_ver)
    return {
        "id": str(mapping.id),
        "source_requirement": _requirement_summary(source, source_fw, source_ver),
        "target_requirement": _requirement_summary(target, target_fw, target_ver),
        "relationship_type": mapping.relationship_type,
        "confidence": mapping.confidence,
        "mapping_source": mapping.mapping_source,
        "notes": mapping.notes,
        "direction": direction,
        "other_requirement": other,
        "created_at": mapping.created_at.isoformat(),
    }


def list_mappings(
    session: Session,
    workspace_id: UUID,
    requirement_id: UUID | None = None,
) -> list[dict[str, object]]:
    statement = select(RequirementMapping).where(
        or_(
            RequirementMapping.workspace_id == workspace_id,
            RequirementMapping.workspace_id.is_(None),
        )
    )
    if requirement_id is not None:
        statement = statement.where(
            or_(
                RequirementMapping.source_requirement_id == requirement_id,
                RequirementMapping.target_requirement_id == requirement_id,
            )
        )
    mappings = session.scalars(statement.order_by(RequirementMapping.created_at.desc())).all()
    return [mapping_data(session, mapping, requirement_id) for mapping in mappings]


def delete_mapping(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    mapping_id: UUID,
) -> None:
    mapping = session.scalar(
        select(RequirementMapping).where(
            RequirementMapping.id == mapping_id,
            RequirementMapping.workspace_id == workspace_id,
        )
    )
    if mapping is None:
        raise CrosswalkNotFound("Requirement mapping not found.")
    before = mapping_data(session, mapping)
    source_id = mapping.source_requirement_id
    session.delete(mapping)
    record_activity(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="FRAMEWORK_REQUIREMENT",
        entity_id=source_id,
        action_code="CROSSWALK_REMOVED",
        before=before,
        after=None,
    )
