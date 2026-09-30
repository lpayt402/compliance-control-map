from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.selectable import Subquery

from app.models import (
    AssessmentTag,
    Framework,
    FrameworkDomain,
    FrameworkRequirement,
    FrameworkVersion,
    RequirementAssessment,
    RequirementControlMapping,
    RequirementDocument,
    RequirementEvidence,
    RequirementNote,
    StatusDefinition,
    Tag,
    User,
)
from app.services.activity import record_activity


class AssessmentNotFound(LookupError):
    pass


class AssessmentValidationError(ValueError):
    pass


class RevisionConflict(RuntimeError):
    def __init__(self, current_revision: int) -> None:
        super().__init__("assessment revision conflict")
        self.current_revision = current_revision


@dataclass(frozen=True)
class RequirementFilters:
    search: str | None = None
    statuses: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    owners: tuple[UUID, ...] = ()
    assignees: tuple[UUID, ...] = ()
    applicability: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    overdue: bool = False
    framework_slug: str | None = None
    requirement_id: UUID | None = None
    offset: int = 0
    limit: int = 200


def _tag_names(session: Session, assessment_id: UUID) -> list[str]:
    return list(
        session.scalars(
            select(Tag.name)
            .join(AssessmentTag, AssessmentTag.tag_id == Tag.id)
            .where(AssessmentTag.assessment_id == assessment_id)
            .order_by(Tag.name)
        )
    )


def _snapshot(session: Session, assessment: RequirementAssessment) -> dict[str, object]:
    return {
        "status_code": assessment.status_code,
        "applicability": assessment.applicability,
        "owner_user_id": str(assessment.owner_user_id) if assessment.owner_user_id else None,
        "assignee_user_id": (
            str(assessment.assignee_user_id) if assessment.assignee_user_id else None
        ),
        "due_date": assessment.due_date.isoformat() if assessment.due_date else None,
        "implementation_notes": assessment.implementation_notes,
        "tags": _tag_names(session, assessment.id),
        "revision": assessment.revision,
    }


class AssessmentService:
    def __init__(
        self,
        session: Session,
        workspace_id: UUID,
        actor_user_id: UUID | None,
    ) -> None:
        self.session = session
        self.workspace_id = workspace_id
        self.actor_user_id = actor_user_id

    def _assessment(self, requirement_id: UUID) -> RequirementAssessment:
        assessment = self.session.scalar(
            select(RequirementAssessment).where(
                RequirementAssessment.workspace_id == self.workspace_id,
                RequirementAssessment.requirement_id == requirement_id,
            )
        )
        if assessment is None:
            raise AssessmentNotFound("Requirement assessment not found.")
        return assessment

    def _validate_status(self, status_code: str) -> None:
        valid = self.session.scalar(
            select(StatusDefinition.id).where(
                StatusDefinition.workspace_id == self.workspace_id,
                StatusDefinition.scope == "REQUIREMENT",
                StatusDefinition.code == status_code,
            )
        )
        if valid is None:
            raise AssessmentValidationError("Unknown requirement status.")

    def _validate_user(self, user_id: UUID | None) -> None:
        if user_id is None:
            return
        valid = self.session.scalar(
            select(User.id).where(
                User.id == user_id,
                User.workspace_id == self.workspace_id,
            )
        )
        if valid is None:
            raise AssessmentValidationError("Owner or assignee is outside this workspace.")

    def _replace_tags(self, assessment: RequirementAssessment, names: list[str]) -> None:
        normalized = sorted({name.strip().casefold() for name in names if name.strip()})
        self.session.query(AssessmentTag).filter(
            AssessmentTag.assessment_id == assessment.id
        ).delete(synchronize_session=False)
        for name in normalized:
            tag = self.session.scalar(
                select(Tag).where(Tag.workspace_id == self.workspace_id, Tag.name == name)
            )
            if tag is None:
                tag = Tag(workspace_id=self.workspace_id, name=name)
                self.session.add(tag)
                self.session.flush()
            self.session.add(
                AssessmentTag(
                    workspace_id=self.workspace_id,
                    assessment_id=assessment.id,
                    tag_id=tag.id,
                )
            )
        self.session.flush()

    def update(
        self,
        requirement_id: UUID,
        changes: dict[str, object],
        *,
        expected_revision: int,
    ) -> RequirementAssessment:
        assessment = self._assessment(requirement_id)
        if assessment.revision != expected_revision:
            raise RevisionConflict(assessment.revision)
        before = _snapshot(self.session, assessment)

        status_supplied = "status_code" in changes
        applicability_supplied = "applicability" in changes
        status_code = str(changes.get("status_code", assessment.status_code))
        applicability = str(changes.get("applicability", assessment.applicability))
        if applicability not in {"UNDETERMINED", "APPLICABLE", "NOT_APPLICABLE"}:
            raise AssessmentValidationError("Unknown applicability value.")
        if status_supplied:
            self._validate_status(status_code)
        if status_supplied and applicability_supplied:
            one_is_na = (status_code == "NOT_APPLICABLE") != (
                applicability == "NOT_APPLICABLE"
            )
            if one_is_na:
                raise AssessmentValidationError(
                    "Not-applicable status and applicability must agree."
                )
        elif status_supplied and status_code == "NOT_APPLICABLE":
            applicability = "NOT_APPLICABLE"
        elif applicability_supplied and applicability == "NOT_APPLICABLE":
            status_code = "NOT_APPLICABLE"
        elif status_supplied and assessment.status_code == "NOT_APPLICABLE":
            applicability = "APPLICABLE"
        elif applicability_supplied and assessment.applicability == "NOT_APPLICABLE":
            status_code = "NOT_ASSESSED"

        owner = changes.get("owner_user_id", assessment.owner_user_id)
        assignee = changes.get("assignee_user_id", assessment.assignee_user_id)
        if owner is not None and not isinstance(owner, UUID):
            raise AssessmentValidationError("Invalid owner.")
        if assignee is not None and not isinstance(assignee, UUID):
            raise AssessmentValidationError("Invalid assignee.")
        self._validate_user(owner)
        self._validate_user(assignee)

        assessment.status_code = status_code
        assessment.applicability = applicability
        assessment.owner_user_id = owner
        assessment.assignee_user_id = assignee
        if "due_date" in changes:
            due_date = changes["due_date"]
            if due_date is not None and not isinstance(due_date, date):
                raise AssessmentValidationError("Invalid due date.")
            assessment.due_date = due_date
        if "implementation_notes" in changes:
            assessment.implementation_notes = str(changes["implementation_notes"])
        if "tags" in changes:
            tags = changes["tags"]
            if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
                raise AssessmentValidationError("Invalid tags.")
            self._replace_tags(assessment, tags)
        assessment.revision += 1
        assessment.updated_at = datetime.now(UTC)
        self.session.flush()
        after = _snapshot(self.session, assessment)
        record_activity(
            self.session,
            workspace_id=self.workspace_id,
            actor_user_id=self.actor_user_id,
            entity_type="FRAMEWORK_REQUIREMENT",
            entity_id=requirement_id,
            action_code="ASSESSMENT_UPDATED",
            before=before,
            after=after,
        )
        return assessment


def _count_subquery(
    model: (
        type[RequirementDocument]
        | type[RequirementEvidence]
        | type[RequirementControlMapping]
    ),
    label: str,
    workspace_id: UUID,
) -> Subquery:
    return (
        select(model.requirement_id.label("requirement_id"), func.count(model.id).label(label))
        .where(model.workspace_id == workspace_id)
        .group_by(model.requirement_id)
        .subquery()
    )


def list_requirements(
    session: Session,
    workspace_id: UUID,
    filters: RequirementFilters,
) -> tuple[list[dict[str, object]], int]:
    owner = aliased(User)
    assignee = aliased(User)
    document_counts = _count_subquery(
        RequirementDocument,
        "document_count",
        workspace_id,
    )
    evidence_counts = _count_subquery(
        RequirementEvidence,
        "evidence_count",
        workspace_id,
    )
    control_counts = _count_subquery(
        RequirementControlMapping,
        "control_count",
        workspace_id,
    )
    statement = (
        select(
            FrameworkRequirement,
            FrameworkDomain,
            FrameworkVersion,
            Framework,
            RequirementAssessment,
            owner,
            assignee,
            func.coalesce(document_counts.c.document_count, 0),
            func.coalesce(evidence_counts.c.evidence_count, 0),
            func.coalesce(control_counts.c.control_count, 0),
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
        .outerjoin(owner, owner.id == RequirementAssessment.owner_user_id)
        .outerjoin(assignee, assignee.id == RequirementAssessment.assignee_user_id)
        .outerjoin(document_counts, document_counts.c.requirement_id == FrameworkRequirement.id)
        .outerjoin(evidence_counts, evidence_counts.c.requirement_id == FrameworkRequirement.id)
        .outerjoin(control_counts, control_counts.c.requirement_id == FrameworkRequirement.id)
        .where(RequirementAssessment.workspace_id == workspace_id)
    )
    statement = _apply_filters(statement, filters)
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    total = session.scalar(count_statement) or 0
    rows = session.execute(
        statement.order_by(
            Framework.name,
            FrameworkDomain.sort_order,
            FrameworkRequirement.sort_order,
        )
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    assessment_ids = [row[4].id for row in rows]
    tags: dict[UUID, list[str]] = {assessment_id: [] for assessment_id in assessment_ids}
    if assessment_ids:
        for assessment_id, name in session.execute(
            select(AssessmentTag.assessment_id, Tag.name)
            .join(Tag, Tag.id == AssessmentTag.tag_id)
            .where(AssessmentTag.assessment_id.in_(assessment_ids))
            .order_by(Tag.name)
        ):
            tags[assessment_id].append(name)
    return [
        _compose_requirement(tuple(row), tags[cast(RequirementAssessment, row[4]).id])
        for row in rows
    ], total


def _apply_filters(statement: Select[Any], filters: RequirementFilters) -> Select[Any]:
    if filters.requirement_id:
        statement = statement.where(FrameworkRequirement.id == filters.requirement_id)
    if filters.framework_slug:
        statement = statement.where(Framework.slug == filters.framework_slug)
    if filters.statuses:
        statement = statement.where(RequirementAssessment.status_code.in_(filters.statuses))
    if filters.domains:
        statement = statement.where(FrameworkDomain.external_id.in_(filters.domains))
    if filters.owners:
        statement = statement.where(RequirementAssessment.owner_user_id.in_(filters.owners))
    if filters.assignees:
        statement = statement.where(RequirementAssessment.assignee_user_id.in_(filters.assignees))
    if filters.applicability:
        statement = statement.where(
            RequirementAssessment.applicability.in_(filters.applicability)
        )
    if filters.tags:
        statement = statement.where(
            exists(
                select(AssessmentTag.assessment_id)
                .join(Tag, Tag.id == AssessmentTag.tag_id)
                .where(
                    AssessmentTag.assessment_id == RequirementAssessment.id,
                    Tag.name.in_(filters.tags),
                )
            )
        )
    if filters.overdue:
        statement = statement.where(
            RequirementAssessment.due_date < date.today(),
            RequirementAssessment.status_code != "NOT_APPLICABLE",
        )
    if filters.search:
        pattern = f"%{filters.search.strip().casefold()}%"
        statement = statement.where(
            or_(
                func.lower(FrameworkRequirement.external_id).like(pattern),
                func.lower(FrameworkRequirement.title).like(pattern),
                func.lower(FrameworkRequirement.summary).like(pattern),
                exists(
                    select(AssessmentTag.assessment_id)
                    .join(Tag, Tag.id == AssessmentTag.tag_id)
                    .where(
                        AssessmentTag.assessment_id == RequirementAssessment.id,
                        func.lower(Tag.name).like(pattern),
                    )
                ),
            )
        )
    return statement


def _user_summary(user: User | None) -> dict[str, object] | None:
    if user is None:
        return None
    return {"id": str(user.id), "display_name": user.display_name, "email": user.email}


def _compose_requirement(row: tuple[object, ...], tags: list[str]) -> dict[str, object]:
    requirement = cast(FrameworkRequirement, row[0])
    domain = cast(FrameworkDomain, row[1])
    version = cast(FrameworkVersion, row[2])
    framework = cast(Framework, row[3])
    assessment = cast(RequirementAssessment, row[4])
    owner = cast(User | None, row[5])
    assignee = cast(User | None, row[6])
    document_count = cast(int, row[7])
    evidence_count = cast(int, row[8])
    control_count = cast(int, row[9])
    return {
        "id": str(requirement.id),
        "external_id": requirement.external_id,
        "title": requirement.title,
        "summary": requirement.summary,
        "guidance": requirement.guidance,
        "source_reference": requirement.source_reference,
        "parent_id": str(requirement.parent_id) if requirement.parent_id else None,
        "framework": {
            "id": str(framework.id),
            "slug": framework.slug,
            "name": framework.name,
            "version": version.version,
        },
        "domain": {
            "id": str(domain.id),
            "external_id": domain.external_id,
            "name": domain.name,
        },
        "assessment": {
            "id": str(assessment.id),
            "status_code": assessment.status_code,
            "applicability": assessment.applicability,
            "owner": _user_summary(owner),
            "assignee": _user_summary(assignee),
            "due_date": assessment.due_date.isoformat() if assessment.due_date else None,
            "implementation_notes": assessment.implementation_notes,
            "tags": tags,
            "revision": assessment.revision,
            "updated_at": assessment.updated_at.isoformat(),
        },
        "document_count": document_count,
        "evidence_count": evidence_count,
        "control_count": control_count,
        "last_updated": assessment.updated_at.isoformat(),
    }


def create_note(
    session: Session,
    workspace_id: UUID,
    requirement_id: UUID,
    actor_user_id: UUID | None,
    body: str,
) -> RequirementNote:
    assessment = session.scalar(
        select(RequirementAssessment).where(
            RequirementAssessment.workspace_id == workspace_id,
            RequirementAssessment.requirement_id == requirement_id,
        )
    )
    if assessment is None:
        raise AssessmentNotFound("Requirement assessment not found.")
    note = RequirementNote(
        workspace_id=workspace_id,
        assessment_id=assessment.id,
        author_user_id=actor_user_id,
        body=body,
    )
    session.add(note)
    session.flush()
    record_activity(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="FRAMEWORK_REQUIREMENT",
        entity_id=requirement_id,
        action_code="NOTE_CREATED",
        before=None,
        after={"note_id": str(note.id), "body": note.body},
    )
    return note


def update_note(
    session: Session,
    workspace_id: UUID,
    requirement_id: UUID,
    note_id: UUID,
    actor_user_id: UUID | None,
    body: str,
) -> RequirementNote:
    note = session.scalar(
        select(RequirementNote)
        .join(RequirementAssessment, RequirementAssessment.id == RequirementNote.assessment_id)
        .where(
            RequirementNote.id == note_id,
            RequirementNote.workspace_id == workspace_id,
            RequirementAssessment.requirement_id == requirement_id,
        )
    )
    if note is None:
        raise AssessmentNotFound("Requirement note not found.")
    before: dict[str, object] = {"note_id": str(note.id), "body": note.body}
    note.body = body
    note.edited_at = datetime.now(UTC)
    session.flush()
    record_activity(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="FRAMEWORK_REQUIREMENT",
        entity_id=requirement_id,
        action_code="NOTE_UPDATED",
        before=before,
        after={"note_id": str(note.id), "body": note.body},
    )
    return note


def list_notes(
    session: Session,
    workspace_id: UUID,
    requirement_id: UUID,
) -> list[RequirementNote]:
    return list(
        session.scalars(
            select(RequirementNote)
            .join(RequirementAssessment, RequirementAssessment.id == RequirementNote.assessment_id)
            .where(
                RequirementNote.workspace_id == workspace_id,
                RequirementAssessment.requirement_id == requirement_id,
            )
            .order_by(RequirementNote.created_at.desc())
        )
    )
