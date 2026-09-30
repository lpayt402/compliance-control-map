from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, select

from app.core.database import DatabaseManager
from app.frameworks.importer import import_pack
from app.models import FrameworkRequirement, RequirementAssessment, Workspace
from app.services.assessments import AssessmentService, RevisionConflict

PACK_PATH = Path(__file__).parents[3] / "framework-packs" / "soc2"


def test_not_applicable_status_and_applicability_stay_consistent(
    alembic_config: Config,
    migrated_engine: Engine,
) -> None:
    manager = DatabaseManager(alembic_config.get_main_option("sqlalchemy.url"))
    import_pack(PACK_PATH, manager)
    with manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        requirement = session.scalar(
            select(FrameworkRequirement).where(FrameworkRequirement.external_id == "CC6.1")
        )
        assert workspace is not None and requirement is not None
        service = AssessmentService(session, workspace.id, actor_user_id=None)

        updated = service.update(
            requirement.id,
            {"status_code": "NOT_APPLICABLE"},
            expected_revision=1,
        )

        assert updated.status_code == "NOT_APPLICABLE"
        assert updated.applicability == "NOT_APPLICABLE"
        assert updated.revision == 2


def test_stale_revision_does_not_overwrite_a_newer_assessment(
    alembic_config: Config,
    migrated_engine: Engine,
) -> None:
    manager = DatabaseManager(alembic_config.get_main_option("sqlalchemy.url"))
    import_pack(PACK_PATH, manager)
    with manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        requirement = session.scalar(
            select(FrameworkRequirement).where(FrameworkRequirement.external_id == "CC6.2")
        )
        assert workspace is not None and requirement is not None
        service = AssessmentService(session, workspace.id, actor_user_id=None)
        service.update(requirement.id, {"status_code": "GAP"}, expected_revision=1)

        with pytest.raises(RevisionConflict) as conflict:
            service.update(
                requirement.id,
                {"implementation_notes": "This stale edit must not win."},
                expected_revision=1,
            )

        assert conflict.value.current_revision == 2
        current = session.scalar(
            select(RequirementAssessment).where(
                RequirementAssessment.requirement_id == requirement.id
            )
        )
        assert current is not None
        assert current.implementation_notes == ""
