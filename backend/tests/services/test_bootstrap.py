from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, select

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.core.passwords import verify_password
from app.frameworks.importer import import_pack
from app.models import User
from app.services.bootstrap import ensure_bootstrap_admin

PACK_PATH = Path(__file__).parents[3] / "framework-packs" / "soc2"


def test_team_bootstrap_creates_one_hashed_administrator(
    alembic_config: Config,
    migrated_engine: Engine,
) -> None:
    del migrated_engine
    database_url = alembic_config.get_main_option("sqlalchemy.url")
    manager = DatabaseManager(database_url)
    import_pack(PACK_PATH, manager)
    settings = Settings(
        auth_mode="local",
        database_url=database_url,
        bootstrap_admin_email="ADMIN@example.com",
        bootstrap_admin_display_name="Workshop Admin",
        bootstrap_admin_password="a durable bootstrap passphrase",  # noqa: S106
    )

    assert ensure_bootstrap_admin(manager, settings) is True
    assert ensure_bootstrap_admin(manager, settings) is False
    cleared_settings = Settings(
        auth_mode="local",
        database_url=database_url,
        bootstrap_admin_email="",
        bootstrap_admin_password="",
    )
    assert ensure_bootstrap_admin(manager, cleared_settings) is False

    with manager.session() as session:
        users = list(session.scalars(select(User)))
        assert len(users) == 1
        assert users[0].normalized_email == "admin@example.com"
        assert users[0].password_hash != "a durable bootstrap passphrase"  # noqa: S105
        assert verify_password("a durable bootstrap passphrase", users[0].password_hash)
    manager.dispose()


def test_fresh_team_workspace_rejects_cleared_bootstrap_credentials(
    alembic_config: Config,
    migrated_engine: Engine,
) -> None:
    del migrated_engine
    database_url = alembic_config.get_main_option("sqlalchemy.url")
    manager = DatabaseManager(database_url)
    import_pack(PACK_PATH, manager)
    settings = Settings(
        auth_mode="local",
        database_url=database_url,
        bootstrap_admin_email="",
        bootstrap_admin_password="",
    )

    with pytest.raises(RuntimeError, match="Fresh team mode needs"):
        ensure_bootstrap_admin(manager, settings)
    manager.dispose()
