from collections.abc import Generator
from pathlib import Path
from uuid import UUID

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.core.passwords import hash_password
from app.frameworks.importer import import_pack
from app.main import create_app
from app.models import ActivityEvent, Session, User, Workspace

PACK_PATH = Path(__file__).parents[3] / "framework-packs" / "soc2"
ORIGIN = "http://testserver"


@pytest.fixture
def auth_app(
    alembic_config: Config,
    migrated_engine: Engine,
    tmp_path: Path,
) -> Generator[tuple[TestClient, DatabaseManager, UUID, UUID], None, None]:
    database_url = alembic_config.get_main_option("sqlalchemy.url")
    manager = DatabaseManager(database_url)
    import_pack(PACK_PATH, manager)
    with manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assert workspace is not None
        admin = User(
            workspace_id=workspace.id,
            email="admin@example.com",
            normalized_email="admin@example.com",
            display_name="Local Admin",
            password_hash=hash_password("a sturdy admin passphrase"),
            role="ADMIN",
            can_login=True,
        )
        viewer = User(
            workspace_id=workspace.id,
            email="viewer@example.com",
            normalized_email="viewer@example.com",
            display_name="Evidence Viewer",
            password_hash=hash_password("a sturdy viewer passphrase"),
            role="VIEWER",
            can_login=True,
        )
        session.add_all([admin, viewer])
        session.flush()
        admin_id = admin.id
        viewer_id = viewer.id
    settings = Settings(
        app_env="test",
        auth_mode="local",
        database_url=database_url,
        data_dir=tmp_path,
        storage_root=tmp_path / "files",
        allowed_origins=[ORIGIN],
        allowed_hosts=["testserver"],
    )
    with TestClient(create_app(settings=settings, database_manager=manager)) as client:
        yield client, manager, admin_id, viewer_id
    manager.dispose()


def _login(client: TestClient, email: str, password: str) -> dict[str, object]:
    preflight = client.get("/api/v1/auth/csrf")
    assert preflight.status_code == 200
    token = preflight.json()["data"]["csrf_token"]
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN, "X-CSRF-Token": token},
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_login_creates_hash_only_session_and_logout_revokes_it(
    auth_app: tuple[TestClient, DatabaseManager, UUID, UUID],
) -> None:
    client, manager, admin_id, _viewer_id = auth_app

    payload = _login(client, "ADMIN@example.com", "a sturdy admin passphrase")

    assert payload["user"]["id"] == str(admin_id)
    assert payload["user"]["role"] == "ADMIN"
    session_cookie = client.cookies.get("ccm_session")
    assert session_cookie is not None
    with manager.session() as session:
        stored = session.scalar(select(Session).where(Session.user_id == admin_id))
        assert stored is not None
        assert stored.secret_hash != session_cookie
        assert len(stored.secret_hash) == 64

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    csrf_token = payload["csrf_token"]
    logout = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": str(csrf_token)},
    )
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    with manager.session() as session:
        stored = session.scalar(select(Session).where(Session.user_id == admin_id))
        assert stored is not None
        assert stored.revoked_at is not None


def test_csrf_and_origin_are_required_even_for_login(
    auth_app: tuple[TestClient, DatabaseManager, UUID, UUID],
) -> None:
    client, _manager, _admin_id, _viewer_id = auth_app
    token = client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]
    credentials = {
        "email": "admin@example.com",
        "password": "a sturdy admin passphrase",
    }

    missing_token = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json=credentials,
    )
    bad_origin = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://attacker.invalid", "X-CSRF-Token": token},
        json=credentials,
    )

    assert missing_token.status_code == 403
    assert bad_origin.status_code == 403


def test_viewer_cannot_list_users_and_self_demote_is_rejected(
    auth_app: tuple[TestClient, DatabaseManager, UUID, UUID],
) -> None:
    client, manager, admin_id, _viewer_id = auth_app
    _login(client, "viewer@example.com", "a sturdy viewer passphrase")
    assert client.get("/api/v1/users").status_code == 403

    client.cookies.clear()
    admin_session = _login(client, "admin@example.com", "a sturdy admin passphrase")
    assert client.get("/api/v1/users").status_code == 200
    changed = client.patch(
        f"/api/v1/users/{admin_id}",
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": str(admin_session["csrf_token"]),
        },
        json={"role": "VIEWER"},
    )
    assert changed.status_code == 409
    assert client.get("/api/v1/auth/me").status_code == 200
    with manager.session() as session:
        assert session.scalar(select(User.role).where(User.id == admin_id)) == "ADMIN"


def test_authenticated_viewer_can_use_minimal_user_directory(
    auth_app: tuple[TestClient, DatabaseManager, UUID, UUID],
) -> None:
    client, _manager, _admin_id, _viewer_id = auth_app
    _login(client, "viewer@example.com", "a sturdy viewer passphrase")

    response = client.get("/api/v1/users/directory")

    assert response.status_code == 200
    assert response.json()["data"] == [
        {"id": response.json()["data"][0]["id"], "display_name": "Evidence Viewer"},
        {"id": response.json()["data"][1]["id"], "display_name": "Local Admin"},
    ]


def test_admin_user_lifecycle_is_guarded_audited_and_revokes_sessions(
    auth_app: tuple[TestClient, DatabaseManager, UUID, UUID],
) -> None:
    client, manager, admin_id, viewer_id = auth_app
    _login(client, "viewer@example.com", "a sturdy viewer passphrase")
    viewer_cookie = client.cookies.get("ccm_session")
    assert viewer_cookie is not None

    client.cookies.clear()
    admin_session = _login(client, "admin@example.com", "a sturdy admin passphrase")
    headers = {
        "Origin": ORIGIN,
        "X-CSRF-Token": str(admin_session["csrf_token"]),
    }

    listed = client.get("/api/v1/users")
    assert listed.status_code == 200
    assert {item["is_disabled"] for item in listed.json()["data"]} == {False}

    self_disable = client.patch(
        f"/api/v1/users/{admin_id}",
        headers=headers,
        json={"is_disabled": True},
    )
    self_demote = client.patch(
        f"/api/v1/users/{admin_id}",
        headers=headers,
        json={"role": "VIEWER"},
    )
    self_password_reset = client.patch(
        f"/api/v1/users/{admin_id}",
        headers=headers,
        json={"password": "a replacement admin passphrase"},
    )
    assert self_disable.status_code == 409
    assert self_demote.status_code == 409
    assert self_password_reset.status_code == 409

    changed = client.patch(
        f"/api/v1/users/{viewer_id}",
        headers=headers,
        json={
            "role": "EDITOR",
            "is_disabled": True,
            "password": "a replacement viewer passphrase",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["data"]["role"] == "EDITOR"
    assert changed.json()["data"]["is_disabled"] is True

    client.cookies.clear()
    client.cookies.set("ccm_session", viewer_cookie)
    assert client.get("/api/v1/auth/me").status_code == 401

    client.cookies.clear()
    admin_session = _login(client, "admin@example.com", "a sturdy admin passphrase")
    headers["X-CSRF-Token"] = str(admin_session["csrf_token"])
    reactivated = client.patch(
        f"/api/v1/users/{viewer_id}",
        headers=headers,
        json={"is_disabled": False},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["data"]["is_disabled"] is False

    client.cookies.clear()
    _login(client, "viewer@example.com", "a replacement viewer passphrase")

    client.cookies.clear()
    admin_session = _login(client, "admin@example.com", "a sturdy admin passphrase")
    headers["X-CSRF-Token"] = str(admin_session["csrf_token"])
    deleted = client.delete(f"/api/v1/users/{viewer_id}", headers=headers)
    assert deleted.status_code == 204

    activity_response = client.get("/api/v1/users/activity")
    assert activity_response.status_code == 200
    deletion = next(
        item
        for item in activity_response.json()["data"]
        if item["action_code"] == "USER_DELETED"
    )
    assert deletion["before"]["email"] == "viewer@example.com"
    assert "password" not in str(deletion).casefold()

    with manager.session() as session:
        assert session.get(User, viewer_id) is None
        events = list(
            session.scalars(
                select(ActivityEvent).where(
                    ActivityEvent.entity_type == "USER",
                    ActivityEvent.entity_id == viewer_id,
                )
            )
        )
        assert {
            "USER_DEACTIVATED",
            "USER_REACTIVATED",
            "USER_PASSWORD_RESET",
            "USER_DELETED",
        }.issubset({event.action_code for event in events})
        assert "password" not in str(
            [(event.before_snapshot, event.after_snapshot) for event in events]
        ).casefold()


def test_user_changes_password_with_current_password_and_sessions_are_revoked(
    auth_app: tuple[TestClient, DatabaseManager, UUID, UUID],
) -> None:
    client, manager, _admin_id, viewer_id = auth_app
    viewer_session = _login(client, "viewer@example.com", "a sturdy viewer passphrase")
    headers = {
        "Origin": ORIGIN,
        "X-CSRF-Token": str(viewer_session["csrf_token"]),
    }

    wrong = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": "not the current password",
            "new_password": "a replacement viewer passphrase",
        },
    )
    assert wrong.status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 200

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": "a sturdy viewer passphrase",
            "new_password": "a replacement viewer passphrase",
        },
    )
    assert changed.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401

    client.cookies.clear()
    token = client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]
    old_login = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN, "X-CSRF-Token": token},
        json={
            "email": "viewer@example.com",
            "password": "a sturdy viewer passphrase",
        },
    )
    assert old_login.status_code == 401
    client.cookies.clear()
    _login(client, "viewer@example.com", "a replacement viewer passphrase")

    with manager.session() as session:
        events = list(
            session.scalars(
                select(ActivityEvent).where(
                    ActivityEvent.entity_type == "USER",
                    ActivityEvent.entity_id == viewer_id,
                    ActivityEvent.action_code == "PASSWORD_CHANGED",
                )
            )
        )
        assert len(events) == 1
        assert "password" not in str(
            [(event.before_snapshot, event.after_snapshot) for event in events]
        ).casefold()


def test_login_failures_are_generic_and_throttled(
    auth_app: tuple[TestClient, DatabaseManager, UUID, UUID],
) -> None:
    client, _manager, _admin_id, _viewer_id = auth_app
    token = client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]
    headers = {"Origin": ORIGIN, "X-CSRF-Token": token}

    responses = [
        client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": "nobody@example.com", "password": "a wrong passphrase here"},
        )
        for _ in range(6)
    ]

    assert all(response.status_code == 401 for response in responses[:5])
    assert responses[5].status_code == 429
    assert responses[0].json()["detail"] == "Invalid email or password."


def test_production_session_cookies_use_host_prefix_and_secure_flags(
    auth_app: tuple[TestClient, DatabaseManager, UUID, UUID],
) -> None:
    _client, manager, _admin_id, _viewer_id = auth_app
    settings = Settings(
        app_env="production",
        auth_mode="local",
        database_url=str(manager.engine.url),
        bind_host="127.0.0.1",
        allowed_origins=["https://testserver"],
        allowed_hosts=["testserver"],
    )
    with TestClient(
        create_app(settings=settings, database_manager=manager),
        base_url="https://testserver",
    ) as client:
        preflight = client.get("/api/v1/auth/csrf")
        token = preflight.json()["data"]["csrf_token"]
        login = client.post(
            "/api/v1/auth/login",
            headers={"Origin": "https://testserver", "X-CSRF-Token": token},
            json={
                "email": "admin@example.com",
                "password": "a sturdy admin passphrase",
            },
        )

    assert preflight.status_code == 200
    assert "__Host-ccm_csrf=" in preflight.headers["set-cookie"]
    cookie = login.headers["set-cookie"]
    assert login.status_code == 200
    assert "__Host-ccm_session=" in cookie
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Domain=" not in cookie
