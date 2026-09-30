import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from alembic.config import Config
from sqlalchemy import Engine, func, select

from alembic import command
from app.core.database import DatabaseManager
from app.core.passwords import hash_password
from app.frameworks.importer import import_pack
from app.models import (
    ControlNote,
    Document,
    FrameworkRequirement,
    InferenceProviderProfile,
    InferenceRun,
    OrganizationalControl,
    RequirementAssessment,
    RequirementNote,
    User,
    Workspace,
)
from app.services.demo import load_demo_data
from app.services.exports import (
    ArchiveValidationError,
    RestoreTargetNotEmpty,
    create_workspace_export,
    restore_workspace_export,
)
from app.storage import LocalFilesystemStorage

PACK_PATH = Path(__file__).parents[3] / "framework-packs" / "soc2"
DEMO_PATH = Path(__file__).parents[2] / "demo-files"


def _as_v1_archive(archive: bytes) -> bytes:
    output = BytesIO()
    with ZipFile(BytesIO(archive)) as source, ZipFile(
        output, "w", ZIP_DEFLATED
    ) as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == "manifest.json":
                manifest = json.loads(content)
                manifest["schema_version"] = 1
                content = json.dumps(manifest).encode()
            elif info.filename == "workspace.json":
                data = json.loads(content)
                data["schema_version"] = 1
                data.pop("control_notes", None)
                for note in data.get("notes", []):
                    note.pop("kind", None)
                    note.pop("title", None)
                    note.pop("contact_user_id", None)
                    note.pop("revision", None)
                content = json.dumps(data).encode()
            target.writestr(info.filename, content)
    return output.getvalue()


def test_export_is_portable_hashed_and_excludes_authentication_secrets(
    alembic_config: Config,
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    manager = DatabaseManager(alembic_config.get_main_option("sqlalchemy.url"))
    import_pack(PACK_PATH, manager)
    storage = LocalFilesystemStorage(tmp_path / "files")
    load_demo_data(manager, storage, DEMO_PATH)
    with manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assert workspace is not None
        provider = InferenceProviderProfile(
            workspace_id=workspace.id,
            provider_identifier="must-not-export-provider",
            display_name="Operational provider",
            base_url="https://models.example.test/v1",
            model_id="must-not-export-model",
            api_mode="CHAT_COMPLETIONS",
            capabilities={"streaming": True},
            timeout_seconds=60,
            tls_policy="REQUIRED",
            data_policy="EXTERNAL_ALLOWED",
            secret_ref="env:CCM_MUST_NOT_EXPORT_KEY",  # noqa: S106 - reference only
            enabled=False,
            is_default=False,
        )
        session.add(provider)
        session.flush()
        session.add(
            InferenceRun(
                workspace_id=workspace.id,
                provider_profile_id=provider.id,
                provider_identifier_snapshot=provider.provider_identifier,
                provider_display_name_snapshot=provider.display_name,
                base_url_snapshot=provider.base_url,
                model_id_snapshot=provider.model_id,
                agent_id="compliance-assistant",
                skill_id="control-review",
                skill_version="1.0.0",
                record_references=[],
                instruction="must-not-export-instruction",
                context_digest="0" * 64,
                status="COMPLETED",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                output_text="must-not-export-output",
                cancellation_requested=False,
                created_at=datetime.now(UTC),
            )
        )
        session.flush()
        archive = create_workspace_export(session, storage, workspace.id)

    with ZipFile(BytesIO(archive)) as bundle:
        names = set(bundle.namelist())
        assert {"manifest.json", "workspace.json"}.issubset(names)
        manifest = json.loads(bundle.read("manifest.json"))
        workspace_data = bundle.read("workspace.json")
        combined = archive + workspace_data
        assert b"password_hash" not in combined
        assert b"csrf_secret" not in combined
        assert b"secret_hash" not in combined
        assert b"must-not-export-provider" not in combined
        assert b"CCM_MUST_NOT_EXPORT_KEY" not in combined
        assert b"must-not-export-instruction" not in combined
        assert b"must-not-export-output" not in combined
        for item in manifest["files"]:
            member = item["archive_path"]
            path = PurePosixPath(member)
            assert not path.is_absolute() and ".." not in path.parts
            assert hashlib.sha256(bundle.read(member)).hexdigest() == item["sha256"]


def test_v2_export_includes_typed_requirement_and_control_resources(
    alembic_config: Config,
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    manager = DatabaseManager(alembic_config.get_main_option("sqlalchemy.url"))
    import_pack(PACK_PATH, manager)
    storage = LocalFilesystemStorage(tmp_path / "files")
    load_demo_data(manager, storage, DEMO_PATH)
    with manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assessment = session.scalar(select(RequirementAssessment))
        control = session.scalar(select(OrganizationalControl))
        assert workspace is not None and assessment is not None and control is not None
        session.add(
            RequirementNote(
                workspace_id=workspace.id,
                assessment_id=assessment.id,
                kind="CONTACT",
                title="Assessment contact",
                body="Coordinate evidence collection.",
            )
        )
        session.add(
            ControlNote(
                workspace_id=workspace.id,
                control_id=control.id,
                kind="PLAYBOOK",
                title="Evidence review",
                body="Review and retain the signed report.",
            )
        )
        session.flush()
        archive = create_workspace_export(session, storage, workspace.id)

    with ZipFile(BytesIO(archive)) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        data = json.loads(bundle.read("workspace.json"))
    assert manifest["schema_version"] == data["schema_version"] == 2
    assert data["notes"][-1]["kind"] == "CONTACT"
    assert data["notes"][-1]["title"] == "Assessment contact"
    assert data["notes"][-1]["revision"] == 1
    assert data["control_notes"][0]["kind"] == "PLAYBOOK"
    manager.dispose()


def test_restore_accepts_v1_resources_with_safe_defaults(
    alembic_config: Config,
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    source_manager = DatabaseManager(alembic_config.get_main_option("sqlalchemy.url"))
    import_pack(PACK_PATH, source_manager)
    source_storage = LocalFilesystemStorage(tmp_path / "source-files-v1")
    load_demo_data(source_manager, source_storage, DEMO_PATH)
    with source_manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assessment = session.scalar(select(RequirementAssessment))
        assert workspace is not None and assessment is not None
        session.add(
            RequirementNote(
                workspace_id=workspace.id,
                assessment_id=assessment.id,
                body="Legacy note text.",
            )
        )
        session.flush()
        archive = _as_v1_archive(
            create_workspace_export(session, source_storage, workspace.id)
        )

    target_url = f"sqlite:///{tmp_path / 'target-v1.db'}"
    target_config = Config(Path(__file__).parents[2] / "alembic.ini")
    target_config.set_main_option("script_location", str(Path(__file__).parents[2] / "alembic"))
    target_config.set_main_option("sqlalchemy.url", target_url)
    command.upgrade(target_config, "head")
    target_manager = DatabaseManager(target_url)
    import_pack(PACK_PATH, target_manager)
    with target_manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assert workspace is not None
        restore_workspace_export(
            session,
            LocalFilesystemStorage(tmp_path / "target-files-v1"),
            workspace.id,
            archive,
        )
    with target_manager.session() as session:
        note = session.scalar(
            select(RequirementNote).where(
                RequirementNote.body == "Legacy note text."
            )
        )
        assert note is not None
        assert note.kind == "NOTE"
        assert note.title == ""
        assert note.contact_user_id is None
        assert note.revision == 1
        assert session.scalar(select(ControlNote)) is None
    target_manager.dispose()
    source_manager.dispose()


def test_restore_rejects_traversal_and_populated_targets(
    alembic_config: Config,
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    manager = DatabaseManager(alembic_config.get_main_option("sqlalchemy.url"))
    import_pack(PACK_PATH, manager)
    storage = LocalFilesystemStorage(tmp_path / "files")
    malicious = BytesIO()
    with ZipFile(malicious, "w", ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", json.dumps({"schema_version": 1, "files": []}))
        bundle.writestr("workspace.json", "{}")
        bundle.writestr("../escape.txt", "nope")
    with manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assert workspace is not None
        with pytest.raises(ArchiveValidationError, match="unsafe"):
            restore_workspace_export(session, storage, workspace.id, malicious.getvalue())
        session.add(
            User(
                workspace_id=workspace.id,
                display_name="Existing user",
                role="VIEWER",
                can_login=False,
            )
        )
        session.flush()
        with pytest.raises(RestoreTargetNotEmpty):
            restore_workspace_export(session, storage, workspace.id, b"not reached")


def test_export_restores_metadata_mappings_and_files_into_untouched_installation(
    alembic_config: Config,
    migrated_engine: Engine,
    tmp_path: Path,
) -> None:
    source_manager = DatabaseManager(alembic_config.get_main_option("sqlalchemy.url"))
    import_pack(PACK_PATH, source_manager)
    source_storage = LocalFilesystemStorage(tmp_path / "source-files")
    load_demo_data(source_manager, source_storage, DEMO_PATH)
    with source_manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assessment = session.scalar(select(RequirementAssessment))
        control = session.scalar(select(OrganizationalControl))
        contact = (
            session.scalar(select(User).where(User.workspace_id == workspace.id))
            if workspace
            else None
        )
        assert workspace is not None and assessment is not None and control is not None
        session.add(
            RequirementNote(
                workspace_id=workspace.id,
                assessment_id=assessment.id,
                contact_user_id=contact.id if contact else None,
                kind="CONTACT",
                title="Portable contact",
                body="Coordinate the portable assessment.",
            )
        )
        session.add(
            ControlNote(
                workspace_id=workspace.id,
                control_id=control.id,
                kind="PLAYBOOK",
                title="Portable playbook",
                body="Collect and retain the signed report.",
            )
        )
        session.flush()
        archive = create_workspace_export(session, source_storage, workspace.id)

    target_url = f"sqlite:///{tmp_path / 'target.db'}"
    target_config = Config(Path(__file__).parents[2] / "alembic.ini")
    target_config.set_main_option(
        "script_location",
        str(Path(__file__).parents[2] / "alembic"),
    )
    target_config.set_main_option("sqlalchemy.url", target_url)
    command.upgrade(target_config, "head")
    target_manager = DatabaseManager(target_url)
    import_pack(PACK_PATH, target_manager)
    target_storage = LocalFilesystemStorage(tmp_path / "target-files")
    with target_manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assert workspace is not None
        session.add(
            User(
                workspace_id=workspace.id,
                email="admin@example.com",
                normalized_email="admin@example.com",
                display_name="Target Admin",
                password_hash=hash_password("a target-only administrator passphrase"),
                role="ADMIN",
                can_login=True,
            )
        )
    with target_manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assert workspace is not None
        restore_workspace_export(session, target_storage, workspace.id, archive)
    with target_manager.session() as session:
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
        assert states["CC6.1"] == "READY"
        assert states["CC7.1"] == "GAP"
        assert session.scalar(select(func.count()).select_from(Document)) == 1
        target_admin = session.scalar(
            select(User).where(User.normalized_email == "admin@example.com")
        )
        assert target_admin is not None
        assert target_admin.can_login is True
        assert target_admin.is_disabled is False
        restored_contact = session.scalar(
            select(RequirementNote).where(RequirementNote.title == "Portable contact")
        )
        restored_playbook = session.scalar(
            select(ControlNote).where(ControlNote.title == "Portable playbook")
        )
        assert restored_contact is not None
        assert restored_contact.kind == "CONTACT"
        assert restored_contact.contact_user_id is not None
        assert restored_playbook is not None
        assert restored_playbook.kind == "PLAYBOOK"
    assert len(list((tmp_path / "target-files").iterdir())) == 2
    target_manager.dispose()
    source_manager.dispose()
