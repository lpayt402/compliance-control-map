from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, func, select

from app.core.database import DatabaseManager
from app.frameworks.importer import FrameworkPackConflict, import_pack
from app.frameworks.pack_schema import load_pack
from app.models import FrameworkRequirement, FrameworkVersion, RequirementAssessment

PACK_PATH = Path(__file__).parents[3] / "framework-packs" / "soc2"


def test_importing_soc2_twice_is_idempotent(
    alembic_config: Config,
    migrated_engine: Engine,
) -> None:
    manager = DatabaseManager(alembic_config.get_main_option("sqlalchemy.url"))

    first = import_pack(PACK_PATH, manager)
    second = import_pack(PACK_PATH, manager)

    assert first.created is True
    assert second.created is False
    with manager.session() as session:
        assert session.scalar(select(func.count()).select_from(FrameworkVersion)) == 1
        assert session.scalar(select(func.count()).select_from(FrameworkRequirement)) == 61
        assert session.scalar(select(func.count()).select_from(RequirementAssessment)) == 61


def test_changed_pack_with_same_version_is_rejected(
    alembic_config: Config,
    migrated_engine: Engine,
) -> None:
    manager = DatabaseManager(alembic_config.get_main_option("sqlalchemy.url"))
    pack = load_pack(PACK_PATH)
    import_pack(pack, manager)
    changed = pack.model_copy(
        update={
            "framework": pack.framework.model_copy(
                update={"description": f"{pack.framework.description} changed"}
            )
        }
    )

    with pytest.raises(FrameworkPackConflict, match="different content"):
        import_pack(changed, manager)
