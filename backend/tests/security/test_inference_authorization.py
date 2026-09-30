from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.core.passwords import hash_password
from app.frameworks.importer import import_pack
from app.main import create_app
from app.models import InferenceRun, User, Workspace

ORIGIN = "http://testserver"
REPOSITORY_ROOT = Path(__file__).parents[3]
PACK_PATH = REPOSITORY_ROOT / "framework-packs" / "soc2"


@pytest.fixture
def team_inference_app(
    alembic_config: Config,
    migrated_engine: Engine,
    tmp_path: Path,
) -> Generator[tuple[TestClient, DatabaseManager, UUID], None, None]:
    database_url = alembic_config.get_main_option("sqlalchemy.url")
    assert database_url is not None
    manager = DatabaseManager(database_url)
    import_pack(PACK_PATH, manager)
    with manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assert workspace is not None
        users = [
            User(
                workspace_id=workspace.id,
                email=f"{role.casefold()}@example.com",
                normalized_email=f"{role.casefold()}@example.com",
                display_name=f"Test {role.title()}",
                password_hash=hash_password(f"a sturdy {role.casefold()} passphrase"),
                role=role,
                can_login=True,
            )
            for role in ("ADMIN", "EDITOR", "VIEWER")
        ]
        session.add_all(users)
        session.flush()
        editor_id = users[1].id
    settings = Settings(
        app_env="test",
        auth_mode="local",
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
        yield client, manager, editor_id
    manager.dispose()


def _login(client: TestClient, role: str) -> dict[str, object]:
    token = client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN, "X-CSRF-Token": token},
        json={
            "email": f"{role.casefold()}@example.com",
            "password": f"a sturdy {role.casefold()} passphrase",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, dict)
    return data


def _provider_payload() -> dict[str, object]:
    return {
        "provider_identifier": "team-local",
        "display_name": "Team local model",
        "base_url": "http://127.0.0.1:11434/v1",
        "model_id": "fake",
        "capabilities": {"streaming": True},
        "tls_policy": "PLAINTEXT_LOCAL_ONLY",
        "data_policy": "LOCAL_ONLY",
        "enabled": True,
        "is_default": True,
    }


def test_viewer_cannot_see_or_initiate_model_assistance(
    team_inference_app: tuple[TestClient, DatabaseManager, UUID],
) -> None:
    client, _manager, _editor_id = team_inference_app
    _login(client, "VIEWER")

    assert client.get("/api/v1/inference/status").status_code == 403
    assert client.get("/api/v1/inference/providers").status_code == 403
    assert client.get("/api/v1/inference/skills").status_code == 403
    assert client.get("/api/v1/inference/runs").status_code == 403


def test_editor_can_read_assistance_configuration_but_not_mutate_provider(
    team_inference_app: tuple[TestClient, DatabaseManager, UUID],
) -> None:
    client, _manager, _editor_id = team_inference_app
    session = _login(client, "EDITOR")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": str(session["csrf_token"])}

    assert client.get("/api/v1/inference/status").status_code == 200
    assert client.get("/api/v1/inference/skills").status_code == 200
    assert (
        client.post(
            "/api/v1/inference/providers",
            headers=headers,
            json=_provider_payload(),
        ).status_code
        == 403
    )


def test_admin_provider_mutation_requires_csrf_and_run_lookup_is_workspace_scoped(
    team_inference_app: tuple[TestClient, DatabaseManager, UUID],
) -> None:
    client, manager, editor_id = team_inference_app
    admin_session = _login(client, "ADMIN")
    assert (
        client.post("/api/v1/inference/providers", json=_provider_payload()).status_code
        == 403
    )
    created = client.post(
        "/api/v1/inference/providers",
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": str(admin_session["csrf_token"]),
        },
        json=_provider_payload(),
    )
    assert created.status_code == 201

    with manager.session() as session:
        foreign_workspace = Workspace(
            slug="foreign-run-workspace",
            name="Foreign",
            timezone="UTC",
            locale="en-US",
        )
        session.add(foreign_workspace)
        session.flush()
        run = InferenceRun(
            workspace_id=foreign_workspace.id,
            user_id=editor_id,
            provider_identifier_snapshot="foreign",
            provider_display_name_snapshot="Foreign",
            base_url_snapshot="https://foreign.invalid/v1",
            model_id_snapshot="foreign",
            agent_id="compliance-assistant",
            skill_id="control-review",
            skill_version="1.0.0",
            record_references=[],
            instruction="foreign secret context",
            context_digest="0" * 64,
            status="COMPLETED",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            output_text="foreign output",
            cancellation_requested=False,
            created_at=datetime.now(UTC),
        )
        session.add(run)
        session.flush()
        foreign_run_id = run.id

    assert client.get(f"/api/v1/inference/runs/{foreign_run_id}").status_code == 404
    assert client.get(f"/api/v1/inference/runs/{uuid4()}").status_code == 404
