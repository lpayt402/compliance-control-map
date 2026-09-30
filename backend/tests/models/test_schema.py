import pytest
from sqlalchemy import Engine, inspect


def test_initial_schema_has_catalog_control_crosswalk_and_library_tables(
    migrated_engine: Engine,
) -> None:
    tables = set(inspect(migrated_engine).get_table_names())

    assert {
        "frameworks",
        "framework_versions",
        "framework_domains",
        "framework_requirements",
        "workspaces",
        "requirement_assessments",
        "status_definitions",
        "organizational_controls",
        "requirement_control_mappings",
        "requirement_mappings",
        "documents",
        "evidence",
        "stored_files",
        "control_documents",
        "control_evidence",
        "requirement_documents",
        "requirement_evidence",
        "users",
        "sessions",
        "requirement_notes",
        "activity_events",
        "tags",
        "assessment_tags",
        "control_tags",
        "inference_provider_profiles",
        "inference_runs",
    } <= tables


def test_catalog_and_assessment_uniqueness_are_database_constraints(
    migrated_engine: Engine,
) -> None:
    inspector = inspect(migrated_engine)
    requirement_constraints = {
        item["name"] for item in inspector.get_unique_constraints("framework_requirements")
    }
    assessment_constraints = {
        item["name"] for item in inspector.get_unique_constraints("requirement_assessments")
    }

    assert "uq_framework_requirement_version_external_id" in requirement_constraints
    assert "uq_requirement_assessment_workspace_requirement" in assessment_constraints


def test_crosswalk_rejects_self_links_and_duplicate_directed_relationships(
    migrated_engine: Engine,
) -> None:
    inspector = inspect(migrated_engine)
    checks = {item["name"] for item in inspector.get_check_constraints("requirement_mappings")}
    uniques = {item["name"] for item in inspector.get_unique_constraints("requirement_mappings")}

    assert "ck_requirement_mapping_distinct" in checks
    assert "uq_requirement_mapping_direction_type" in uniques


def test_sqlite_foreign_keys_are_enabled(migrated_engine: Engine) -> None:
    if migrated_engine.dialect.name != "sqlite":
        pytest.skip("SQLite connection pragma is not applicable to PostgreSQL.")
    with migrated_engine.connect() as connection:
        enabled = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()

    assert enabled == 1
