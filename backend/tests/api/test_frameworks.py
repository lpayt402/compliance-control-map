from pathlib import Path

from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.frameworks.importer import import_pack
from app.main import create_app

PACK_PATH = Path(__file__).parents[3] / "framework-packs" / "soc2"


def test_framework_api_returns_imported_generic_structure(
    alembic_config: Config,
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    database_url = alembic_config.get_main_option("sqlalchemy.url")
    manager = DatabaseManager(database_url)
    import_pack(PACK_PATH, manager)
    settings = Settings(
        app_env="test",
        database_url=database_url,
        data_dir=tmp_path,
        storage_root=tmp_path / "files",
    )
    client = TestClient(create_app(settings=settings, database_manager=manager))

    response = client.get("/api/v1/frameworks")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload[0]["slug"] == "soc2"
    assert payload[0]["active_version"]["version"] == "2017-tsc-pof-2022"
    assert payload[0]["active_version"]["requirement_count"] == 61
