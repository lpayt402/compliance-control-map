from fastapi.testclient import TestClient

from app.models import User, Workspace
from tests.api.test_requirements import _by_external_id, _csrf_headers


def _create_contact(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/users",
        headers=_csrf_headers(client),
        json={
            "email": "contact@example.com",
            "display_name": "Review Contact",
            "password": "a sufficiently long contact password",
            "role": "VIEWER",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_requirement_notes_can_be_added_edited_and_seen_in_activity(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    requirement = _by_external_id(client, "CC8.1")
    headers = _csrf_headers(client)

    created = client.post(
        f"/api/v1/requirements/{requirement['id']}/notes",
        headers=headers,
        json={"body": "Confirm change samples with engineering."},
    )
    assert created.status_code == 201
    note = created.json()["data"]
    changed = client.patch(
        f"/api/v1/requirements/{requirement['id']}/notes/{note['id']}",
        headers=headers,
        json={
            "revision": 1,
            "body": "Confirm approved change samples with engineering.",
        },
    )

    assert changed.status_code == 200
    notes = client.get(f"/api/v1/requirements/{requirement['id']}/notes").json()["data"]
    activity = client.get(f"/api/v1/requirements/{requirement['id']}/activity").json()[
        "data"
    ]
    assert notes[0]["body"] == "Confirm approved change samples with engineering."
    assert [event["action_code"] for event in activity] == ["NOTE_UPDATED", "NOTE_CREATED"]
    assert activity[0]["before"]["body"] == "Confirm change samples with engineering."


def test_requirement_resources_support_typed_revisioned_crud(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    requirement = _by_external_id(client, "CC8.1")
    contact = _create_contact(client)
    headers = _csrf_headers(client)

    created = client.post(
        f"/api/v1/requirements/{requirement['id']}/notes",
        headers=headers,
        json={
            "kind": "CONTACT",
            "title": "Change review contact",
            "body": "Coordinate the quarterly review.",
            "contact_user_id": contact["id"],
        },
    )
    assert created.status_code == 201
    resource = created.json()["data"]
    assert resource["kind"] == "CONTACT"
    assert resource["title"] == "Change review contact"
    assert resource["contact_user"]["id"] == contact["id"]
    assert resource["revision"] == 1

    changed = client.patch(
        f"/api/v1/requirements/{requirement['id']}/notes/{resource['id']}",
        headers=headers,
        json={"revision": 1, "body": "Coordinate the monthly review."},
    )
    assert changed.status_code == 200
    assert changed.json()["data"]["revision"] == 2

    conflict = client.patch(
        f"/api/v1/requirements/{requirement['id']}/notes/{resource['id']}",
        headers=headers,
        json={"revision": 1, "body": "Stale edit."},
    )
    assert conflict.status_code == 409
    assert conflict.headers["content-type"].startswith("application/problem+json")
    assert conflict.json()["current"]["revision"] == 2

    removed = client.delete(
        f"/api/v1/requirements/{requirement['id']}/notes/{resource['id']}?revision=2",
        headers=headers,
    )
    assert removed.status_code == 204
    assert client.get(f"/api/v1/requirements/{requirement['id']}/notes").json()["data"] == []

    actions = [
        event["action_code"]
        for event in client.get(
            f"/api/v1/requirements/{requirement['id']}/activity"
        ).json()["data"]
    ]
    assert actions[:3] == ["CONTACT_DELETED", "CONTACT_UPDATED", "CONTACT_CREATED"]


def test_typed_resource_validation_is_explicit(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    requirement = _by_external_id(client, "CC8.1")
    contact = _create_contact(client)
    headers = _csrf_headers(client)

    missing_title = client.post(
        f"/api/v1/requirements/{requirement['id']}/notes",
        headers=headers,
        json={"kind": "PLAYBOOK", "body": "Follow the approved change procedure."},
    )
    invalid_contact_use = client.post(
        f"/api/v1/requirements/{requirement['id']}/notes",
        headers=headers,
        json={
            "kind": "NOTE",
            "body": "Plain note",
            "contact_user_id": contact["id"],
        },
    )

    assert missing_title.status_code == 422
    assert invalid_contact_use.status_code == 422


def test_contact_user_ids_are_scoped_without_existence_leaks(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    manager = client.app.state.database
    with manager.session() as session:
        other_workspace = Workspace(slug="other", name="Other workspace")
        session.add(other_workspace)
        session.flush()
        other_contact = User(
            workspace_id=other_workspace.id,
            display_name="Other workspace contact",
            role="VIEWER",
            can_login=False,
        )
        session.add(other_contact)
        session.flush()
        other_contact_id = other_contact.id

    requirement = _by_external_id(client, "CC8.1")
    response = client.post(
        f"/api/v1/requirements/{requirement['id']}/notes",
        headers=_csrf_headers(client),
        json={
            "kind": "CONTACT",
            "title": "External contact",
            "body": "Should not resolve across workspaces.",
            "contact_user_id": str(other_contact_id),
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Contact user not found."
