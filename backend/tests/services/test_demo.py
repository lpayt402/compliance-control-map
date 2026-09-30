from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine, func, select

from app.core.database import DatabaseManager
from app.frameworks.importer import import_pack
from app.models import Document, Evidence, FrameworkRequirement, RequirementAssessment
from app.services.demo import load_demo_data
from app.storage import LocalFilesystemStorage

PACK_PATH = Path(__file__).parents[3] / "framework-packs" / "soc2"
DEMO_PATH = Path(__file__).parents[2] / "demo-files"


def test_demo_load_is_idempotent_and_uses_the_approved_example_states(
    alembic_config: Config,
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    manager = DatabaseManager(alembic_config.get_main_option("sqlalchemy.url"))
    import_pack(PACK_PATH, manager)
    storage = LocalFilesystemStorage(tmp_path / "files")

    first = load_demo_data(manager, storage, DEMO_PATH)
    second = load_demo_data(manager, storage, DEMO_PATH)

    assert first is True
    assert second is False
    with manager.session() as session:
        states = dict(
            session.execute(
                select(FrameworkRequirement.external_id, RequirementAssessment.status_code)
                .join(
                    RequirementAssessment,
                    RequirementAssessment.requirement_id == FrameworkRequirement.id,
                )
                .where(FrameworkRequirement.external_id.in_(["CC6.1", "CC6.2", "CC7.1", "CC8.1"]))
            ).all()
        )
        assert states == {
            "CC6.1": "READY",
            "CC6.2": "PARTIAL",
            "CC7.1": "GAP",
            "CC8.1": "IN_PROGRESS",
        }
        assert session.scalar(select(func.count()).select_from(Document)) == 1
        assert session.scalar(select(func.count()).select_from(Evidence)) == 1
    assert len(list((tmp_path / "files").iterdir())) == 2
