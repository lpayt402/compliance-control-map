import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    ActivityEvent,
    AssessmentTag,
    ControlDocument,
    ControlEvidence,
    ControlNote,
    ControlTag,
    Document,
    Evidence,
    Framework,
    FrameworkDomain,
    FrameworkRequirement,
    FrameworkVersion,
    OrganizationalControl,
    RequirementAssessment,
    RequirementControlMapping,
    RequirementDocument,
    RequirementEvidence,
    RequirementMapping,
    RequirementNote,
    StatusDefinition,
    StoredFile,
    Tag,
    User,
    Workspace,
)
from app.storage import FileStorage

SCHEMA_VERSION = 2
SUPPORTED_RESTORE_SCHEMA_VERSIONS = {1, 2}
MAX_ARCHIVE_MEMBERS = 10_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024


class ArchiveValidationError(ValueError):
    pass


class RestoreTargetNotEmpty(RuntimeError):
    pass


def _domain_external_id(session: Session, domain_id: UUID | None) -> str | None:
    if domain_id is None:
        return None
    domain = session.get(FrameworkDomain, domain_id)
    if domain is None:
        raise ArchiveValidationError("Framework domain hierarchy is incomplete.")
    return domain.external_id


def _requirement_external_id(session: Session, requirement_id: UUID | None) -> str | None:
    if requirement_id is None:
        return None
    requirement = session.get(FrameworkRequirement, requirement_id)
    if requirement is None:
        raise ArchiveValidationError("Framework requirement hierarchy is incomplete.")
    return requirement.external_id


def _note_requirement_id(session: Session, assessment_id: UUID) -> UUID:
    assessment = session.get(RequirementAssessment, assessment_id)
    if assessment is None:
        raise ArchiveValidationError("A requirement note has no assessment.")
    return assessment.requirement_id


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _requirement_reference(
    requirement: FrameworkRequirement,
    framework: Framework,
    version: FrameworkVersion,
) -> dict[str, str]:
    return {
        "framework": framework.slug,
        "version": version.version,
        "external_id": requirement.external_id,
    }


def _requirement_reference_index(
    session: Session,
) -> dict[UUID, dict[str, str]]:
    return {
        requirement.id: _requirement_reference(requirement, framework, version)
        for requirement, framework, version in session.execute(
            select(FrameworkRequirement, Framework, FrameworkVersion)
            .join(
                FrameworkVersion,
                FrameworkVersion.id == FrameworkRequirement.framework_version_id,
            )
            .join(Framework, Framework.id == FrameworkVersion.framework_id)
        )
    }


def _framework_data(session: Session) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for framework in session.scalars(select(Framework).order_by(Framework.slug)):
        versions: list[dict[str, object]] = []
        for version in session.scalars(
            select(FrameworkVersion)
            .where(FrameworkVersion.framework_id == framework.id)
            .order_by(FrameworkVersion.version)
        ):
            domains = [
                {
                    "external_id": domain.external_id,
                    "parent_id": _domain_external_id(session, domain.parent_id),
                    "name": domain.name,
                    "description": domain.description,
                    "sort_order": domain.sort_order,
                }
                for domain in session.scalars(
                    select(FrameworkDomain)
                    .where(FrameworkDomain.framework_version_id == version.id)
                    .order_by(FrameworkDomain.sort_order)
                )
            ]
            domain_ids = {
                domain.id: domain.external_id
                for domain in session.scalars(
                    select(FrameworkDomain).where(
                        FrameworkDomain.framework_version_id == version.id
                    )
                )
            }
            requirements = [
                {
                    "external_id": requirement.external_id,
                    "domain_id": domain_ids[requirement.domain_id],
                    "parent_id": _requirement_external_id(
                        session, requirement.parent_id
                    ),
                    "title": requirement.title,
                    "summary": requirement.summary,
                    "guidance": requirement.guidance,
                    "source_reference": requirement.source_reference,
                    "sort_order": requirement.sort_order,
                }
                for requirement in session.scalars(
                    select(FrameworkRequirement)
                    .where(FrameworkRequirement.framework_version_id == version.id)
                    .order_by(FrameworkRequirement.sort_order)
                )
            ]
            versions.append(
                {
                    "version": version.version,
                    "source_uri": version.source_uri,
                    "source_hash": version.source_hash,
                    "verified_on": version.verified_on.isoformat(),
                    "published_at": (
                        version.published_at.isoformat() if version.published_at else None
                    ),
                    "disclaimer": version.disclaimer,
                    "is_active": version.is_active,
                    "domains": domains,
                    "requirements": requirements,
                }
            )
        result.append(
            {
                "slug": framework.slug,
                "name": framework.name,
                "description": framework.description,
                "versions": versions,
            }
        )
    return result


def _workspace_data(session: Session, workspace_id: UUID) -> dict[str, object]:
    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        raise ArchiveValidationError("Workspace not found.")
    requirement_refs = _requirement_reference_index(session)
    users = list(
        session.scalars(
            select(User).where(User.workspace_id == workspace_id).order_by(User.display_name)
        )
    )
    tags = list(
        session.scalars(select(Tag).where(Tag.workspace_id == workspace_id).order_by(Tag.name))
    )
    assessments = list(
        session.scalars(
            select(RequirementAssessment).where(
                RequirementAssessment.workspace_id == workspace_id
            )
        )
    )
    controls = list(
        session.scalars(
            select(OrganizationalControl).where(
                OrganizationalControl.workspace_id == workspace_id
            )
        )
    )
    documents = list(
        session.scalars(select(Document).where(Document.workspace_id == workspace_id))
    )
    evidence = list(
        session.scalars(select(Evidence).where(Evidence.workspace_id == workspace_id))
    )
    files = list(
        session.scalars(select(StoredFile).where(StoredFile.workspace_id == workspace_id))
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": {
            "slug": workspace.slug,
            "name": workspace.name,
            "timezone": workspace.timezone,
            "locale": workspace.locale,
        },
        "frameworks": _framework_data(session),
        "status_definitions": [
            {
                "scope": item.scope,
                "code": item.code,
                "label": item.label,
                "description": item.description,
                "color_token": item.color_token,
                "icon": item.icon,
                "sort_order": item.sort_order,
                "is_terminal": item.is_terminal,
            }
            for item in session.scalars(
                select(StatusDefinition)
                .where(StatusDefinition.workspace_id == workspace_id)
                .order_by(StatusDefinition.sort_order)
            )
        ],
        "users": [
            {
                "id": str(user.id),
                "email": user.email,
                "normalized_email": user.normalized_email,
                "display_name": user.display_name,
                "role": user.role,
                "is_disabled": user.is_disabled,
            }
            for user in users
        ],
        "tags": [{"id": str(tag.id), "name": tag.name} for tag in tags],
        "assessments": [
            {
                "id": str(item.id),
                "requirement": requirement_refs[item.requirement_id],
                "status_code": item.status_code,
                "applicability": item.applicability,
                "owner_user_id": str(item.owner_user_id) if item.owner_user_id else None,
                "assignee_user_id": (
                    str(item.assignee_user_id) if item.assignee_user_id else None
                ),
                "due_date": item.due_date.isoformat() if item.due_date else None,
                "implementation_notes": item.implementation_notes,
                "revision": item.revision,
                "tags": list(
                    session.scalars(
                        select(Tag.name)
                        .join(AssessmentTag, AssessmentTag.tag_id == Tag.id)
                        .where(AssessmentTag.assessment_id == item.id)
                        .order_by(Tag.name)
                    )
                ),
            }
            for item in assessments
        ],
        "controls": [
            {
                "id": str(item.id),
                "code": item.code,
                "name": item.name,
                "description": item.description,
                "status_code": item.status_code,
                "owner_user_id": str(item.owner_user_id) if item.owner_user_id else None,
                "implementation_notes": item.implementation_notes,
                "revision": item.revision,
                "tags": list(
                    session.scalars(
                        select(Tag.name)
                        .join(ControlTag, ControlTag.tag_id == Tag.id)
                        .where(ControlTag.control_id == item.id)
                        .order_by(Tag.name)
                    )
                ),
            }
            for item in controls
        ],
        "requirement_control_mappings": [
            {
                "id": str(item.id),
                "requirement": requirement_refs[item.requirement_id],
                "control_id": str(item.control_id),
                "coverage": item.coverage,
                "rationale": item.rationale,
            }
            for item in session.scalars(
                select(RequirementControlMapping).where(
                    RequirementControlMapping.workspace_id == workspace_id
                )
            )
        ],
        "requirement_mappings": [
            {
                "id": str(item.id),
                "source_requirement": requirement_refs[item.source_requirement_id],
                "target_requirement": requirement_refs[item.target_requirement_id],
                "relationship_type": item.relationship_type,
                "confidence": item.confidence,
                "mapping_source": item.mapping_source,
                "notes": item.notes,
                "created_by_user_id": (
                    str(item.created_by_user_id) if item.created_by_user_id else None
                ),
            }
            for item in session.scalars(
                select(RequirementMapping).where(
                    RequirementMapping.workspace_id == workspace_id
                )
            )
        ],
        "stored_files": [
            {
                "id": str(item.id),
                "sha256": item.sha256,
                "original_filename": item.original_filename,
                "extension": item.normalized_extension,
                "declared_media_type": item.declared_media_type,
                "detected_media_type": item.detected_media_type,
                "byte_size": item.byte_size,
                "uploaded_by_user_id": (
                    str(item.uploaded_by_user_id) if item.uploaded_by_user_id else None
                ),
            }
            for item in files
        ],
        "documents": [
            {
                "id": str(item.id),
                "stored_file_id": str(item.stored_file_id),
                "name": item.name,
                "document_type": item.document_type,
                "description": item.description,
                "version": item.version,
                "effective_date": (
                    item.effective_date.isoformat() if item.effective_date else None
                ),
                "owner_user_id": str(item.owner_user_id) if item.owner_user_id else None,
                "notes": item.notes,
                "revision": item.revision,
            }
            for item in documents
        ],
        "evidence": [
            {
                "id": str(item.id),
                "stored_file_id": str(item.stored_file_id),
                "name": item.name,
                "description": item.description,
                "evidence_date": item.evidence_date.isoformat() if item.evidence_date else None,
                "owner_user_id": str(item.owner_user_id) if item.owner_user_id else None,
                "notes": item.notes,
                "revision": item.revision,
            }
            for item in evidence
        ],
        "document_requirement_mappings": [
            {
                "requirement": requirement_refs[item.requirement_id],
                "document_id": str(item.document_id),
                "rationale": item.rationale,
            }
            for item in session.scalars(
                select(RequirementDocument).where(
                    RequirementDocument.workspace_id == workspace_id
                )
            )
        ],
        "evidence_requirement_mappings": [
            {
                "requirement": requirement_refs[item.requirement_id],
                "evidence_id": str(item.evidence_id),
                "rationale": item.rationale,
            }
            for item in session.scalars(
                select(RequirementEvidence).where(
                    RequirementEvidence.workspace_id == workspace_id
                )
            )
        ],
        "document_control_mappings": [
            {"control_id": str(item.control_id), "document_id": str(item.document_id)}
            for item in session.scalars(
                select(ControlDocument).where(ControlDocument.workspace_id == workspace_id)
            )
        ],
        "evidence_control_mappings": [
            {"control_id": str(item.control_id), "evidence_id": str(item.evidence_id)}
            for item in session.scalars(
                select(ControlEvidence).where(ControlEvidence.workspace_id == workspace_id)
            )
        ],
        "notes": [
            {
                "id": str(item.id),
                "requirement": requirement_refs[
                    _note_requirement_id(session, item.assessment_id)
                ],
                "author_user_id": (
                    str(item.author_user_id) if item.author_user_id else None
                ),
                "contact_user_id": (
                    str(item.contact_user_id) if item.contact_user_id else None
                ),
                "kind": item.kind,
                "title": item.title,
                "body": item.body,
                "revision": item.revision,
                "created_at": item.created_at.isoformat(),
                "edited_at": item.edited_at.isoformat() if item.edited_at else None,
            }
            for item in session.scalars(
                select(RequirementNote).where(RequirementNote.workspace_id == workspace_id)
            )
        ],
        "control_notes": [
            {
                "id": str(item.id),
                "control_id": str(item.control_id),
                "author_user_id": (
                    str(item.author_user_id) if item.author_user_id else None
                ),
                "contact_user_id": (
                    str(item.contact_user_id) if item.contact_user_id else None
                ),
                "kind": item.kind,
                "title": item.title,
                "body": item.body,
                "revision": item.revision,
                "created_at": item.created_at.isoformat(),
                "edited_at": item.edited_at.isoformat() if item.edited_at else None,
            }
            for item in session.scalars(
                select(ControlNote).where(ControlNote.workspace_id == workspace_id)
            )
        ],
        "activity": [
            {
                "entity_type": item.entity_type,
                "entity_id": str(item.entity_id),
                "action_code": item.action_code,
                "before": item.before_snapshot,
                "after": item.after_snapshot,
                "created_at": item.created_at.isoformat(),
            }
            for item in session.scalars(
                select(ActivityEvent)
                .where(ActivityEvent.workspace_id == workspace_id)
                .order_by(ActivityEvent.created_at)
            )
        ],
    }


def create_workspace_export(
    session: Session,
    storage: FileStorage,
    workspace_id: UUID,
) -> bytes:
    workspace_data = _workspace_data(session, workspace_id)
    files = list(
        session.scalars(select(StoredFile).where(StoredFile.workspace_id == workspace_id))
    )
    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        raise ArchiveValidationError("Workspace not found.")
    manifest_files: list[dict[str, object]] = []
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED, strict_timestamps=False) as bundle:
        bundle.writestr("workspace.json", _json_bytes(workspace_data))
        written_hashes: set[str] = set()
        for file in files:
            archive_path = f"files/{file.sha256}"
            if file.sha256 not in written_hashes:
                with storage.open(file.storage_key) as stream:
                    content = stream.read()
                if hashlib.sha256(content).hexdigest() != file.sha256:
                    raise ArchiveValidationError(
                        f"Stored file digest mismatch for {file.original_filename}."
                    )
                bundle.writestr(archive_path, content)
                written_hashes.add(file.sha256)
            manifest_files.append(
                {
                    "stored_file_id": str(file.id),
                    "archive_path": archive_path,
                    "sha256": file.sha256,
                    "byte_size": file.byte_size,
                }
            )
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "workspace_slug": workspace.slug,
            "files": manifest_files,
        }
        bundle.writestr("manifest.json", _json_bytes(manifest))
    return output.getvalue()


def _ensure_restore_target_empty(session: Session, workspace_id: UUID) -> None:
    users = list(session.scalars(select(User).where(User.workspace_id == workspace_id)))
    if users and not (
        len(users) == 1
        and users[0].role == "ADMIN"
        and users[0].can_login
        and not users[0].is_disabled
    ):
        raise RestoreTargetNotEmpty("Restore requires a fresh workspace with only its Admin.")
    for model in (
        OrganizationalControl,
        Document,
        Evidence,
        RequirementNote,
        ControlNote,
    ):
        if session.scalar(
            select(func.count()).select_from(model).where(model.workspace_id == workspace_id)
        ):
            raise RestoreTargetNotEmpty("Restore requires an untouched workspace.")
    changed = session.scalar(
        select(func.count())
        .select_from(RequirementAssessment)
        .where(
            RequirementAssessment.workspace_id == workspace_id,
            or_(
                RequirementAssessment.status_code != "NOT_ASSESSED",
                RequirementAssessment.applicability != "UNDETERMINED",
                RequirementAssessment.owner_user_id.is_not(None),
                RequirementAssessment.assignee_user_id.is_not(None),
                RequirementAssessment.due_date.is_not(None),
                RequirementAssessment.implementation_notes != "",
            ),
        )
    )
    if changed:
        raise RestoreTargetNotEmpty("Restore requires an untouched workspace.")


def _safe_members(bundle: ZipFile) -> dict[str, bytes]:
    entries = bundle.infolist()
    if len(entries) > MAX_ARCHIVE_MEMBERS:
        raise ArchiveValidationError("Archive contains too many members.")
    if sum(entry.file_size for entry in entries) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise ArchiveValidationError("Archive expands beyond the restore limit.")
    result: dict[str, bytes] = {}
    for entry in entries:
        path = PurePosixPath(entry.filename)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in entry.filename
            or entry.filename in result
        ):
            raise ArchiveValidationError("Archive contains an unsafe member path.")
        result[entry.filename] = bundle.read(entry)
    return result


def _requirement_lookup(
    session: Session,
) -> dict[tuple[str, str, str], FrameworkRequirement]:
    return {
        (framework.slug, version.version, requirement.external_id): requirement
        for requirement, framework, version in session.execute(
            select(FrameworkRequirement, Framework, FrameworkVersion)
            .join(
                FrameworkVersion,
                FrameworkVersion.id == FrameworkRequirement.framework_version_id,
            )
            .join(Framework, Framework.id == FrameworkVersion.framework_id)
        )
    }


def _resolve_requirement(
    lookup: dict[tuple[str, str, str], FrameworkRequirement],
    reference: dict[str, Any],
) -> FrameworkRequirement:
    key = (
        str(reference["framework"]),
        str(reference["version"]),
        str(reference["external_id"]),
    )
    requirement = lookup.get(key)
    if requirement is None:
        raise ArchiveValidationError(f"Required framework criterion is not installed: {key}.")
    return requirement


def restore_workspace_export(
    session: Session,
    storage: FileStorage,
    workspace_id: UUID,
    archive: bytes,
) -> None:
    _ensure_restore_target_empty(session, workspace_id)
    try:
        with ZipFile(BytesIO(archive)) as bundle:
            members = _safe_members(bundle)
    except BadZipFile as error:
        raise ArchiveValidationError("The restore file is not a valid ZIP archive.") from error
    if "manifest.json" not in members or "workspace.json" not in members:
        raise ArchiveValidationError("Archive is missing its manifest or workspace data.")
    try:
        manifest = json.loads(members["manifest.json"])
        data = json.loads(members["workspace.json"])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ArchiveValidationError("Archive metadata is not valid JSON.") from error
    manifest_version = manifest.get("schema_version")
    data_version = data.get("schema_version")
    if (
        manifest_version != data_version
        or manifest_version not in SUPPORTED_RESTORE_SCHEMA_VERSIONS
    ):
        raise ArchiveValidationError("Archive schema version is not supported.")
    for item in manifest.get("files", []):
        path = item.get("archive_path")
        content = members.get(path)
        if content is None:
            raise ArchiveValidationError("Archive is missing a declared file.")
        if len(content) != item.get("byte_size"):
            raise ArchiveValidationError("Archived file size does not match its manifest.")
        if hashlib.sha256(content).hexdigest() != item.get("sha256"):
            raise ArchiveValidationError("Archived file digest does not match its manifest.")

    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        raise ArchiveValidationError("Restore workspace not found.")
    workspace_values = data["workspace"]
    workspace.name = workspace_values["name"]
    workspace.timezone = workspace_values["timezone"]
    workspace.locale = workspace_values["locale"]
    for definition in data.get("status_definitions", []):
        current = session.scalar(
            select(StatusDefinition).where(
                StatusDefinition.workspace_id == workspace_id,
                StatusDefinition.code == definition["code"],
            )
        )
        if current:
            current.label = definition["label"]
            current.description = definition["description"]
            current.color_token = definition["color_token"]
            current.icon = definition["icon"]
            current.sort_order = definition["sort_order"]
            current.is_terminal = definition["is_terminal"]

    existing_users_by_email = {
        user.normalized_email: user
        for user in session.scalars(select(User).where(User.workspace_id == workspace_id))
        if user.normalized_email
    }
    user_ids: dict[str, UUID] = {}
    for item in data.get("users", []):
        existing_user = existing_users_by_email.get(item.get("normalized_email"))
        if existing_user is not None:
            user_ids[item["id"]] = existing_user.id
            continue
        user = User(
            id=UUID(item["id"]),
            workspace_id=workspace_id,
            email=item.get("email"),
            normalized_email=item.get("normalized_email"),
            display_name=item["display_name"],
            password_hash=None,
            role=item["role"],
            can_login=False,
            is_disabled=True,
        )
        session.add(user)
        user_ids[item["id"]] = user.id
    session.flush()
    requirements = _requirement_lookup(session)
    assessment_by_requirement: dict[UUID, RequirementAssessment] = {
        item.requirement_id: item
        for item in session.scalars(
            select(RequirementAssessment).where(
                RequirementAssessment.workspace_id == workspace_id
            )
        )
    }
    tag_by_name: dict[str, Tag] = {}

    def ensure_tag(name: str) -> Tag:
        tag = tag_by_name.get(name)
        if tag is None:
            tag = Tag(workspace_id=workspace_id, name=name)
            session.add(tag)
            session.flush()
            tag_by_name[name] = tag
        return tag

    for item in data.get("assessments", []):
        requirement = _resolve_requirement(requirements, item["requirement"])
        assessment = assessment_by_requirement[requirement.id]
        assessment.status_code = item["status_code"]
        assessment.applicability = item["applicability"]
        assessment.owner_user_id = user_ids.get(item.get("owner_user_id"))
        assessment.assignee_user_id = user_ids.get(item.get("assignee_user_id"))
        assessment.due_date = (
            datetime.fromisoformat(item["due_date"]).date() if item.get("due_date") else None
        )
        assessment.implementation_notes = item["implementation_notes"]
        assessment.revision = item["revision"]
        for name in item.get("tags", []):
            session.add(
                AssessmentTag(
                    workspace_id=workspace_id,
                    assessment_id=assessment.id,
                    tag_id=ensure_tag(name).id,
                )
            )

    control_ids: dict[str, UUID] = {}
    for item in data.get("controls", []):
        control = OrganizationalControl(
            id=UUID(item["id"]),
            workspace_id=workspace_id,
            code=item["code"],
            name=item["name"],
            description=item["description"],
            status_code=item["status_code"],
            owner_user_id=user_ids.get(item.get("owner_user_id")),
            implementation_notes=item["implementation_notes"],
            revision=item["revision"],
        )
        session.add(control)
        session.flush()
        control_ids[item["id"]] = control.id
        for name in item.get("tags", []):
            session.add(
                ControlTag(
                    workspace_id=workspace_id,
                    control_id=control.id,
                    tag_id=ensure_tag(name).id,
                )
            )
    for item in data.get("requirement_control_mappings", []):
        requirement = _resolve_requirement(requirements, item["requirement"])
        session.add(
            RequirementControlMapping(
                id=UUID(item["id"]),
                workspace_id=workspace_id,
                requirement_id=requirement.id,
                control_id=control_ids[item["control_id"]],
                coverage=item["coverage"],
                rationale=item["rationale"],
            )
        )
    for item in data.get("requirement_mappings", []):
        session.add(
            RequirementMapping(
                id=UUID(item["id"]),
                workspace_id=workspace_id,
                source_requirement_id=_resolve_requirement(
                    requirements, item["source_requirement"]
                ).id,
                target_requirement_id=_resolve_requirement(
                    requirements, item["target_requirement"]
                ).id,
                relationship_type=item["relationship_type"],
                confidence=item.get("confidence"),
                mapping_source=item["mapping_source"],
                notes=item["notes"],
                created_by_user_id=user_ids.get(item.get("created_by_user_id")),
            )
        )

    manifest_by_file = {
        item["stored_file_id"]: item for item in manifest.get("files", [])
    }
    file_ids: dict[str, UUID] = {}
    created_storage_keys: list[str] = []
    try:
        for item in data.get("stored_files", []):
            manifest_item = manifest_by_file[item["id"]]
            content = members[manifest_item["archive_path"]]
            stored = storage.put(
                BytesIO(content),
                extension=item["extension"],
                limit=len(content),
            )
            if stored.sha256 != item["sha256"]:
                storage.delete(stored.key)
                raise ArchiveValidationError("Restored file digest changed unexpectedly.")
            created_storage_keys.append(stored.key)
            file = StoredFile(
                id=UUID(item["id"]),
                workspace_id=workspace_id,
                storage_key=stored.key,
                original_filename=item["original_filename"],
                normalized_extension=item["extension"],
                declared_media_type=item["declared_media_type"],
                detected_media_type=item["detected_media_type"],
                byte_size=item["byte_size"],
                sha256=item["sha256"],
                uploaded_by_user_id=user_ids.get(item.get("uploaded_by_user_id")),
            )
            session.add(file)
            file_ids[item["id"]] = file.id
        # The models deliberately avoid ORM relationship coupling, so make FK ordering explicit.
        session.flush()
        document_ids: dict[str, UUID] = {}
        for item in data.get("documents", []):
            document = Document(
                id=UUID(item["id"]),
                workspace_id=workspace_id,
                stored_file_id=file_ids[item["stored_file_id"]],
                name=item["name"],
                document_type=item["document_type"],
                description=item["description"],
                version=item["version"],
                effective_date=(
                    datetime.fromisoformat(item["effective_date"]).date()
                    if item.get("effective_date")
                    else None
                ),
                owner_user_id=user_ids.get(item.get("owner_user_id")),
                notes=item["notes"],
                revision=item["revision"],
            )
            session.add(document)
            document_ids[item["id"]] = document.id
        evidence_ids: dict[str, UUID] = {}
        for item in data.get("evidence", []):
            evidence = Evidence(
                id=UUID(item["id"]),
                workspace_id=workspace_id,
                stored_file_id=file_ids[item["stored_file_id"]],
                name=item["name"],
                description=item["description"],
                evidence_date=(
                    datetime.fromisoformat(item["evidence_date"]).date()
                    if item.get("evidence_date")
                    else None
                ),
                owner_user_id=user_ids.get(item.get("owner_user_id")),
                notes=item["notes"],
                revision=item["revision"],
            )
            session.add(evidence)
            evidence_ids[item["id"]] = evidence.id
        session.flush()
        for item in data.get("document_requirement_mappings", []):
            session.add(
                RequirementDocument(
                    workspace_id=workspace_id,
                    requirement_id=_resolve_requirement(requirements, item["requirement"]).id,
                    document_id=document_ids[item["document_id"]],
                    rationale=item["rationale"],
                )
            )
        for item in data.get("evidence_requirement_mappings", []):
            session.add(
                RequirementEvidence(
                    workspace_id=workspace_id,
                    requirement_id=_resolve_requirement(requirements, item["requirement"]).id,
                    evidence_id=evidence_ids[item["evidence_id"]],
                    rationale=item["rationale"],
                )
            )
        for item in data.get("document_control_mappings", []):
            session.add(
                ControlDocument(
                    workspace_id=workspace_id,
                    control_id=control_ids[item["control_id"]],
                    document_id=document_ids[item["document_id"]],
                )
            )
        for item in data.get("evidence_control_mappings", []):
            session.add(
                ControlEvidence(
                    workspace_id=workspace_id,
                    control_id=control_ids[item["control_id"]],
                    evidence_id=evidence_ids[item["evidence_id"]],
                )
            )
        for item in data.get("notes", []):
            requirement = _resolve_requirement(requirements, item["requirement"])
            assessment = assessment_by_requirement[requirement.id]
            session.add(
                RequirementNote(
                    id=UUID(item["id"]),
                    workspace_id=workspace_id,
                    assessment_id=assessment.id,
                    author_user_id=user_ids.get(item.get("author_user_id")),
                    contact_user_id=user_ids.get(item.get("contact_user_id")),
                    kind=item.get("kind", "NOTE"),
                    title=item.get("title", ""),
                    body=item["body"],
                    revision=item.get("revision", 1),
                    created_at=datetime.fromisoformat(item["created_at"]),
                    edited_at=(
                        datetime.fromisoformat(item["edited_at"])
                        if item.get("edited_at")
                        else None
                    ),
                )
            )
        for item in data.get("control_notes", []):
            session.add(
                ControlNote(
                    id=UUID(item["id"]),
                    workspace_id=workspace_id,
                    control_id=control_ids[item["control_id"]],
                    author_user_id=user_ids.get(item.get("author_user_id")),
                    contact_user_id=user_ids.get(item.get("contact_user_id")),
                    kind=item.get("kind", "NOTE"),
                    title=item.get("title", ""),
                    body=item["body"],
                    revision=item.get("revision", 1),
                    created_at=datetime.fromisoformat(item["created_at"]),
                    edited_at=(
                        datetime.fromisoformat(item["edited_at"])
                        if item.get("edited_at")
                        else None
                    ),
                )
            )
        session.flush()
    except Exception:
        for key in created_storage_keys:
            storage.delete(key)
        raise
