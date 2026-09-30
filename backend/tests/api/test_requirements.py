from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.core.passwords import hash_password
from app.models import User, Workspace

ORIGIN = "http://testserver"


def _csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]
    return {"Origin": ORIGIN, "X-CSRF-Token": token}


def _by_external_id(client: TestClient, external_id: str) -> dict[str, object]:
    response = client.get("/api/v1/requirements", params={"search": external_id})
    assert response.status_code == 200
    matches = [item for item in response.json()["data"] if item["external_id"] == external_id]
    assert len(matches) == 1
    return matches[0]


def test_requirement_list_detail_update_filters_and_counts(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    cc61 = _by_external_id(client, "CC6.1")
    headers = _csrf_headers(client)

    updated = client.patch(
        f"/api/v1/requirements/{cc61['id']}/assessment",
        headers=headers,
        json={
            "status_code": "READY",
            "applicability": "APPLICABLE",
            "implementation_notes": "Quarterly access review and joiner/mover/leaver checks.",
            "due_date": (date.today() + timedelta(days=30)).isoformat(),
            "tags": ["access", "quarterly"],
            "revision": 1,
        },
    )

    assert updated.status_code == 200
    assessment = updated.json()["data"]["assessment"]
    assert assessment["status_code"] == "READY"
    assert assessment["revision"] == 2
    assert assessment["tags"] == ["access", "quarterly"]
    detail = client.get(f"/api/v1/requirements/{cc61['id']}")
    assert detail.status_code == 200
    assert detail.json()["data"]["document_count"] == 0
    assert detail.json()["data"]["evidence_count"] == 0
    activity = client.get(f"/api/v1/requirements/{cc61['id']}/activity").json()["data"]
    assert activity[0]["action_code"] == "ASSESSMENT_UPDATED"
    assert activity[0]["actor_display_name"] is None
    assert "Readiness" in activity[0]["change_summary"]
    assert activity[0]["before"]["status_code"] == "NOT_ASSESSED"
    assert activity[0]["after"]["status_code"] == "READY"

    ready_in_cc6 = client.get(
        "/api/v1/requirements",
        params=[("status", "READY"), ("domain", "CC6")],
    ).json()["data"]
    tag_search = client.get("/api/v1/requirements", params={"search": "quarterly"}).json()[
        "data"
    ]

    assert [item["external_id"] for item in ready_in_cc6] == ["CC6.1"]
    assert [item["external_id"] for item in tag_search] == ["CC6.1"]


def test_filters_are_or_within_a_field_and_and_across_fields(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    headers = _csrf_headers(client)
    cc61 = _by_external_id(client, "CC6.1")
    cc62 = _by_external_id(client, "CC6.2")
    for requirement, status in ((cc61, "READY"), (cc62, "GAP")):
        response = client.patch(
            f"/api/v1/requirements/{requirement['id']}/assessment",
            headers=headers,
            json={"status_code": status, "revision": 1},
        )
        assert response.status_code == 200

    within = client.get(
        "/api/v1/requirements",
        params=[("status", "READY"), ("status", "GAP")],
    ).json()["data"]
    across = client.get(
        "/api/v1/requirements",
        params=[("status", "READY"), ("domain", "CC6")],
    ).json()["data"]

    assert {item["external_id"] for item in within} == {"CC6.1", "CC6.2"}
    assert [item["external_id"] for item in across] == ["CC6.1"]


def test_overdue_excludes_not_applicable_and_revision_conflict_returns_current(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    headers = _csrf_headers(client)
    cc71 = _by_external_id(client, "CC7.1")
    p11 = _by_external_id(client, "P1.1")
    past = (date.today() - timedelta(days=1)).isoformat()

    first = client.patch(
        f"/api/v1/requirements/{cc71['id']}/assessment",
        headers=headers,
        json={"status_code": "GAP", "due_date": past, "revision": 1},
    )
    assert first.status_code == 200
    excluded = client.patch(
        f"/api/v1/requirements/{p11['id']}/assessment",
        headers=headers,
        json={"status_code": "NOT_APPLICABLE", "due_date": past, "revision": 1},
    )
    assert excluded.status_code == 200

    overdue = client.get("/api/v1/requirements", params={"overdue": "true"}).json()["data"]
    stale = client.patch(
        f"/api/v1/requirements/{cc71['id']}/assessment",
        headers=headers,
        json={"implementation_notes": "stale", "revision": 1},
    )

    assert [item["external_id"] for item in overdue] == ["CC7.1"]
    assert stale.status_code == 409
    assert stale.json()["current"] == {"revision": 2}


def test_owner_assignee_notes_and_tags_can_be_cleared(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    manager = client.app.state.database
    with manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assert workspace is not None
        owner = User(
            workspace_id=workspace.id,
            display_name="Control Owner",
            role="EDITOR",
            can_login=False,
        )
        assignee = User(
            workspace_id=workspace.id,
            display_name="Evidence Assignee",
            role="EDITOR",
            can_login=False,
        )
        session.add_all([owner, assignee])
        session.flush()
        owner_id = owner.id
        assignee_id = assignee.id
    requirement = _by_external_id(client, "CC6.3")
    headers = _csrf_headers(client)
    assigned = client.patch(
        f"/api/v1/requirements/{requirement['id']}/assessment",
        headers=headers,
        json={
            "owner_user_id": str(owner_id),
            "assignee_user_id": str(assignee_id),
            "implementation_notes": "Assigned for review.",
            "tags": ["Access", "review"],
            "revision": 1,
        },
    )
    assert assigned.status_code == 200
    assessment = assigned.json()["data"]["assessment"]
    assert assessment["owner"]["display_name"] == "Control Owner"
    assert assessment["assignee"]["display_name"] == "Evidence Assignee"

    cleared = client.patch(
        f"/api/v1/requirements/{requirement['id']}/assessment",
        headers=headers,
        json={
            "owner_user_id": None,
            "assignee_user_id": None,
            "due_date": None,
            "implementation_notes": "",
            "tags": [],
            "revision": 2,
        },
    )
    assert cleared.status_code == 200
    assert cleared.json()["data"]["assessment"]["owner"] is None
    assert cleared.json()["data"]["assessment"]["tags"] == []


def test_requirement_list_query_count_does_not_grow_with_result_size(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    engine = client.app.state.database.engine
    statements: list[str] = []

    def count_statement(*args: object) -> None:
        statements.append(str(args[2]))

    event.listen(engine, "before_cursor_execute", count_statement)
    try:
        client.get("/api/v1/requirements", params={"search": "CC6.1"})
        small_count = len(statements)
        statements.clear()
        client.get("/api/v1/requirements")
        full_count = len(statements)
    finally:
        event.remove(engine, "before_cursor_execute", count_statement)

    assert small_count == full_count


def test_viewer_cannot_change_requirement_assessments(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    manager = client.app.state.database
    with manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assert workspace is not None
        viewer = User(
            workspace_id=workspace.id,
            email="req-viewer@example.com",
            normalized_email="req-viewer@example.com",
            display_name="Read-only Reviewer",
            password_hash=hash_password("a read only reviewer passphrase"),
            role="VIEWER",
            can_login=True,
        )
        session.add(viewer)
    client.app.state.settings.auth_mode = "local"
    client.cookies.clear()
    token = client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]
    login = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN, "X-CSRF-Token": token},
        json={
            "email": "req-viewer@example.com",
            "password": "a read only reviewer passphrase",
        },
    )
    assert login.status_code == 200
    requirement = _by_external_id(client, "CC6.1")
    denied = client.patch(
        f"/api/v1/requirements/{requirement['id']}/assessment",
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": login.json()["data"]["csrf_token"],
        },
        json={"status_code": "READY", "revision": 1},
    )
    assert denied.status_code == 403
    denied_resource = client.post(
        f"/api/v1/requirements/{requirement['id']}/notes",
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": login.json()["data"]["csrf_token"],
        },
        json={"kind": "NOTE", "body": "Viewers cannot add resources."},
    )
    assert denied_resource.status_code == 403
