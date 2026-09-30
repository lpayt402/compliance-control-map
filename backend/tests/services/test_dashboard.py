from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine, select

from app.core.database import DatabaseManager
from app.frameworks.importer import import_pack
from app.models import FrameworkRequirement, RequirementAssessment, Workspace
from app.services.dashboard import calculate_dashboard

PACK_PATH = Path(__file__).parents[3] / "framework-packs" / "soc2"


def test_readiness_excludes_na_and_does_not_fractionally_credit_partial(
    alembic_config: Config,
    migrated_engine: Engine,
) -> None:
    manager = DatabaseManager(alembic_config.get_main_option("sqlalchemy.url"))
    import_pack(PACK_PATH, manager)
    statuses = {
        "CC6.1": "READY",
        "CC6.2": "PARTIAL",
        "CC7.1": "GAP",
        "P1.1": "NOT_APPLICABLE",
    }
    with manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assert workspace is not None
        rows = session.execute(
            select(RequirementAssessment, FrameworkRequirement)
            .join(
                FrameworkRequirement,
                FrameworkRequirement.id == RequirementAssessment.requirement_id,
            )
            .where(RequirementAssessment.workspace_id == workspace.id)
        ).all()
        selected_ids = set(statuses)
        for assessment, requirement in rows:
            if requirement.external_id in statuses:
                assessment.status_code = statuses[requirement.external_id]
                assessment.applicability = (
                    "NOT_APPLICABLE"
                    if assessment.status_code == "NOT_APPLICABLE"
                    else "APPLICABLE"
                )
            elif requirement.external_id not in selected_ids:
                assessment.status_code = "NOT_APPLICABLE"
                assessment.applicability = "NOT_APPLICABLE"

        result = calculate_dashboard(session, workspace.id)

    assert result["counts"]["READY"] == 1
    assert result["denominator"] == 3
    assert result["readiness_percentage"] == 33
    assert result["assessed_percentage"] == 100


def test_empty_applicable_denominator_returns_zero_without_division_error(
    alembic_config: Config,
    migrated_engine: Engine,
) -> None:
    manager = DatabaseManager(alembic_config.get_main_option("sqlalchemy.url"))
    import_pack(PACK_PATH, manager)
    with manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assert workspace is not None
        for assessment in session.scalars(
            select(RequirementAssessment).where(
                RequirementAssessment.workspace_id == workspace.id
            )
        ):
            assessment.status_code = "NOT_APPLICABLE"
            assessment.applicability = "NOT_APPLICABLE"
        result = calculate_dashboard(session, workspace.id)

    assert result["denominator"] == 0
    assert result["readiness_percentage"] == 0
    assert result["assessed_percentage"] == 0
