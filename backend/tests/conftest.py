import os
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from alembic import command
from app.core.config import Settings
from app.core.database import DatabaseManager
from app.frameworks.importer import import_pack
from app.main import create_app

PACK_PATH = Path(__file__).parents[2] / "framework-packs" / "soc2"
ORIGIN = "http://testserver"
REPOSITORY_ROOT = Path(__file__).parents[2]


@pytest.fixture
def alembic_config(tmp_path: Path) -> Generator[Config, None, None]:
    config = Config(Path(__file__).parents[1] / "alembic.ini")
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
    postgres_url = os.getenv("CCM_TEST_DATABASE_URL")
    admin_engine = None
    schema_name = None

    if postgres_url:
        schema_name = f"ccm_test_{uuid4().hex}"
        admin_engine = create_engine(postgres_url, future=True)
        with admin_engine.begin() as connection:
            connection.execute(CreateSchema(schema_name))
        isolated_url = make_url(postgres_url).update_query_dict(
            {"options": f"-csearch_path={schema_name}"}
        )
        rendered_url = isolated_url.render_as_string(hide_password=False)
        # Alembic stores values in ConfigParser, where literal URL escapes use %%.
        config.set_main_option("sqlalchemy.url", rendered_url.replace("%", "%%"))
    else:
        config.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'schema.db'}")

    try:
        yield config
    finally:
        if admin_engine is not None and schema_name is not None:
            with admin_engine.begin() as connection:
                connection.execute(DropSchema(schema_name, cascade=True, if_exists=True))
            admin_engine.dispose()


@pytest.fixture
def migrated_engine(alembic_config: Config) -> Generator[Engine, None, None]:
    command.upgrade(alembic_config, "head")
    manager = DatabaseManager(alembic_config.get_main_option("sqlalchemy.url"))
    try:
        yield manager.engine
    finally:
        manager.dispose()


@pytest.fixture
def requirements_client(
    alembic_config: Config,
    migrated_engine: Engine,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    database_url = alembic_config.get_main_option("sqlalchemy.url")
    manager = DatabaseManager(database_url)
    import_pack(PACK_PATH, manager)
    settings = Settings(
        app_env="test",
        database_url=database_url,
        data_dir=tmp_path,
        storage_root=tmp_path / "files",
        allowed_origins=[ORIGIN],
        allowed_hosts=["testserver"],
    )
    with TestClient(create_app(settings=settings, database_manager=manager)) as client:
        yield client
    manager.dispose()


@pytest.fixture
def inference_client(
    alembic_config: Config,
    migrated_engine: Engine,
    tmp_path: Path,
) -> Generator[tuple[TestClient, DatabaseManager], None, None]:
    database_url = alembic_config.get_main_option("sqlalchemy.url")
    manager = DatabaseManager(database_url)
    import_pack(PACK_PATH, manager)
    settings = Settings(
        app_env="test",
        database_url=database_url,
        data_dir=tmp_path,
        storage_root=tmp_path / "files",
        allowed_origins=[ORIGIN],
        allowed_hosts=["testserver"],
        inference_enabled=True,
        inference_allowed_base_urls=["http://127.0.0.1:11434/v1"],
        inference_agent_root=REPOSITORY_ROOT / "agents",
        inference_skill_root=REPOSITORY_ROOT / "skills",
    )
    with TestClient(create_app(settings=settings, database_manager=manager)) as client:
        yield client, manager
    manager.dispose()
