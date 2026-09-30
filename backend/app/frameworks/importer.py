import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.frameworks.pack_schema import FrameworkPack, load_pack
from app.models import (
    Framework,
    FrameworkDomain,
    FrameworkRequirement,
    FrameworkVersion,
    RequirementAssessment,
    StatusDefinition,
    Workspace,
)


class FrameworkPackConflict(ValueError):
    pass


@dataclass(frozen=True)
class ImportResult:
    framework_id: UUID
    framework_version_id: UUID
    created: bool
    requirement_count: int


REQUIREMENT_STATUSES = (
    ("NOT_ASSESSED", "Not assessed", "neutral", "circle", 10, False),
    ("GAP", "Gap", "danger", "alert", 20, False),
    ("IN_PROGRESS", "In progress", "progress", "wrench", 30, False),
    ("PARTIAL", "Partial", "partial", "half", 40, False),
    ("READY", "Ready", "ready", "check", 50, True),
    ("NOT_APPLICABLE", "Not applicable", "excluded", "minus", 60, True),
)
CONTROL_STATUSES = (
    ("PLANNED", "Planned", "neutral", "circle", 110, False),
    ("IMPLEMENTING", "Implementing", "progress", "wrench", 120, False),
    ("OPERATING", "Operating", "ready", "check", 130, True),
    ("NEEDS_ATTENTION", "Needs attention", "danger", "alert", 140, False),
    ("RETIRED", "Retired", "excluded", "minus", 150, True),
)


def _ensure_workspace_and_statuses(session: Session) -> Workspace:
    workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
    if workspace is None:
        workspace = Workspace(slug="default", name="Compliance Workspace")
        session.add(workspace)
        session.flush()
    existing = set(
        session.scalars(
            select(StatusDefinition.code).where(StatusDefinition.workspace_id == workspace.id)
        )
    )
    for scope, definitions in (
        ("REQUIREMENT", REQUIREMENT_STATUSES),
        ("CONTROL", CONTROL_STATUSES),
    ):
        for code, label, color, icon, order, terminal in definitions:
            if code not in existing:
                session.add(
                    StatusDefinition(
                        workspace_id=workspace.id,
                        scope=scope,
                        code=code,
                        label=label,
                        description="",
                        color_token=color,
                        icon=icon,
                        sort_order=order,
                        is_terminal=terminal,
                    )
                )
    session.flush()
    return workspace


def import_pack(
    source: Path | FrameworkPack,
    manager: DatabaseManager,
) -> ImportResult:
    pack = load_pack(source) if isinstance(source, Path) else source
    source_hash = pack.canonical_hash()
    with manager.session() as session:
        framework = session.scalar(select(Framework).where(Framework.slug == pack.framework.slug))
        if framework is None:
            framework = Framework(
                slug=pack.framework.slug,
                name=pack.framework.name,
                description=pack.framework.description,
            )
            session.add(framework)
            session.flush()

        existing = session.scalar(
            select(FrameworkVersion).where(
                FrameworkVersion.framework_id == framework.id,
                FrameworkVersion.version == pack.framework.version,
            )
        )
        if existing is not None:
            if existing.source_hash != source_hash:
                raise FrameworkPackConflict(
                    "framework version already exists with different content"
                )
            return ImportResult(framework.id, existing.id, False, len(pack.requirements))

        workspace = _ensure_workspace_and_statuses(session)
        version = FrameworkVersion(
            framework_id=framework.id,
            version=pack.framework.version,
            source_uri=pack.framework.source_uri,
            source_hash=source_hash,
            verified_on=date.fromisoformat(pack.framework.verified_on),
            published_at=(
                date.fromisoformat(pack.framework.published_at)
                if pack.framework.published_at
                else None
            ),
            disclaimer=pack.framework.disclaimer,
            imported_at=datetime.now(UTC),
            is_active=True,
        )
        session.add(version)
        session.flush()

        domains: dict[str, FrameworkDomain] = {}
        for domain_def in sorted(pack.domains, key=lambda domain: domain.sort_order):
            domain = FrameworkDomain(
                framework_version_id=version.id,
                external_id=domain_def.external_id,
                name=domain_def.name,
                description=domain_def.description,
                sort_order=domain_def.sort_order,
            )
            session.add(domain)
            session.flush()
            domains[domain_def.external_id] = domain
        for domain_def in pack.domains:
            if domain_def.parent_id is not None:
                domains[domain_def.external_id].parent_id = domains[domain_def.parent_id].id

        requirements: dict[str, FrameworkRequirement] = {}
        for requirement_def in sorted(
            pack.requirements,
            key=lambda requirement: requirement.sort_order,
        ):
            requirement = FrameworkRequirement(
                framework_version_id=version.id,
                domain_id=domains[requirement_def.domain_id].id,
                external_id=requirement_def.external_id,
                title=requirement_def.title,
                summary=requirement_def.summary,
                guidance=requirement_def.guidance,
                source_reference=requirement_def.source_reference,
                sort_order=requirement_def.sort_order,
            )
            session.add(requirement)
            session.flush()
            requirements[requirement_def.external_id] = requirement
        for requirement_def in pack.requirements:
            if requirement_def.parent_id is not None:
                requirements[requirement_def.external_id].parent_id = requirements[
                    requirement_def.parent_id
                ].id

        session.add_all(
            RequirementAssessment(
                workspace_id=workspace.id,
                requirement_id=requirement.id,
                status_code="NOT_ASSESSED",
                applicability="UNDETERMINED",
            )
            for requirement in requirements.values()
        )
        return ImportResult(framework.id, version.id, True, len(requirements))


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a framework pack")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    result = import_pack(args.path, DatabaseManager(Settings().database_url))
    action = "created" if result.created else "already present"
    print(f"{result.requirement_count} requirements; framework version {action}")


if __name__ == "__main__":
    main()
