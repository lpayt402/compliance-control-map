from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_initial_migration_can_upgrade_downgrade_and_upgrade_again(
    alembic_config: Config,
) -> None:
    command.upgrade(alembic_config, "head")
    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    assert "frameworks" in inspect(engine).get_table_names()

    command.downgrade(alembic_config, "base")
    assert "frameworks" not in inspect(engine).get_table_names()

    command.upgrade(alembic_config, "head")
    assert "frameworks" in inspect(engine).get_table_names()
    engine.dispose()


def test_typed_resource_migration_is_additive(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")
    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    inspector = inspect(engine)
    requirement_note_columns = {
        column["name"] for column in inspector.get_columns("requirement_notes")
    }
    assert {"kind", "title", "contact_user_id", "revision"}.issubset(
        requirement_note_columns
    )
    assert "control_notes" in inspector.get_table_names()
    assert {"kind", "title", "contact_user_id", "revision"}.issubset(
        {column["name"] for column in inspector.get_columns("control_notes")}
    )
    engine.dispose()


def test_inference_history_migration_is_additive_and_non_secret(
    alembic_config: Config,
) -> None:
    command.upgrade(alembic_config, "20260824_0002")
    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    before = set(inspect(engine).get_table_names())

    command.upgrade(alembic_config, "head")
    inspector = inspect(engine)
    assert before <= set(inspector.get_table_names())
    assert {"inference_provider_profiles", "inference_runs"} <= set(
        inspector.get_table_names()
    )
    provider_columns = {
        column["name"] for column in inspector.get_columns("inference_provider_profiles")
    }
    assert "secret_ref" in provider_columns
    assert not {"api_key", "secret_value", "authorization_header"} & provider_columns
    run_columns = {column["name"] for column in inspector.get_columns("inference_runs")}
    assert not {"raw_request", "raw_response", "system_prompt", "tool_payloads"} & run_columns
    engine.dispose()
