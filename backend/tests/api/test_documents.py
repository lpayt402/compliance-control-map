from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import StoredFile, User, Workspace
from tests.api.test_controls import _create_control
from tests.api.test_requirements import _by_external_id, _csrf_headers


def test_document_upload_maps_one_file_to_many_requirements_and_downloads_as_attachment(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    cc61 = _by_external_id(client, "CC6.1")
    cc62 = _by_external_id(client, "CC6.2")
    response = client.post(
        "/api/v1/documents",
        headers=_csrf_headers(client),
        data={
            "name": "Access Control Policy",
            "document_type": "POLICY",
            "description": "Defines account lifecycle expectations.",
            "version": "1.0",
            "requirement_ids": [cc61["id"], cc62["id"]],
        },
        files={"file": ("access-policy.txt", b"demo policy", "text/plain")},
    )

    assert response.status_code == 201
    document = response.json()["data"]
    assert {item["external_id"] for item in document["requirements"]} == {"CC6.1", "CC6.2"}
    assert client.get(f"/api/v1/requirements/{cc61['id']}").json()["data"][
        "document_count"
    ] == 1
    manager = client.app.state.database
    with manager.session() as session:
        assert session.query(StoredFile).count() == 1

    download = client.get(f"/api/v1/documents/{document['id']}/download")
    assert download.status_code == 200
    assert download.content == b"demo policy"
    assert download.headers["content-disposition"].startswith("attachment;")
    assert download.headers["x-content-type-options"] == "nosniff"


def test_document_response_includes_the_workspace_owner_display_name(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    with client.app.state.database.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        assert workspace is not None
        owner = User(workspace_id=workspace.id, display_name="Policy Owner", role="EDITOR")
        session.add(owner)
        session.flush()
        owner_id = owner.id

    response = client.post(
        "/api/v1/documents",
        headers=_csrf_headers(client),
        data={"name": "Owned policy", "document_type": "POLICY", "owner_user_id": str(owner_id)},
        files={"file": ("owned-policy.txt", b"approved", "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["data"]["owner"] == {
        "id": str(owner_id),
        "display_name": "Policy Owner",
        "email": None,
    }


def test_document_can_be_mapped_after_upload_without_copying_bytes(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    requirement = _by_external_id(client, "CC5.2")
    headers = _csrf_headers(client)
    uploaded = client.post(
        "/api/v1/documents",
        headers=headers,
        data={"name": "Security Policy", "document_type": "POLICY"},
        files={"file": ("security.txt", b"one stored policy", "text/plain")},
    ).json()["data"]
    mapped = client.post(
        f"/api/v1/documents/{uploaded['id']}/requirements",
        headers=headers,
        json={"requirement_ids": [requirement["id"]], "rationale": "Policy commitment."},
    )

    assert mapped.status_code == 200
    from_requirement = client.get(
        f"/api/v1/requirements/{requirement['id']}/documents"
    ).json()["data"]
    assert from_requirement[0]["id"] == uploaded["id"]
    assert len(list(client.app.state.settings.storage_root.iterdir())) == 1


def test_document_links_can_be_managed_from_requirement_and_control(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    requirement = _by_external_id(client, "CC5.2")
    control = _create_control(client)
    headers = _csrf_headers(client)
    document = client.post(
        "/api/v1/documents",
        headers=headers,
        data={"name": "Incident plan", "document_type": "PLAN"},
        files={"file": ("incident.txt", b"approved plan", "text/plain")},
    ).json()["data"]

    first = client.post(
        f"/api/v1/requirements/{requirement['id']}/documents",
        headers=headers,
        json={"document_ids": [document["id"]], "rationale": "Required plan."},
    )
    duplicate = client.post(
        f"/api/v1/requirements/{requirement['id']}/documents",
        headers=headers,
        json={"document_ids": [document["id"]], "rationale": "Required plan."},
    )
    control_link = client.post(
        f"/api/v1/controls/{control['id']}/documents",
        headers=headers,
        json={"document_ids": [document["id"]]},
    )
    assert first.status_code == duplicate.status_code == control_link.status_code == 200
    assert client.get(f"/api/v1/controls/{control['id']}/documents").json()["data"][0][
        "id"
    ] == document["id"]

    requirement_detach = client.delete(
        f"/api/v1/requirements/{requirement['id']}/documents/{document['id']}",
        headers=headers,
    )
    repeated_detach = client.delete(
        f"/api/v1/requirements/{requirement['id']}/documents/{document['id']}",
        headers=headers,
    )
    control_detach = client.delete(
        f"/api/v1/controls/{control['id']}/documents/{document['id']}",
        headers=headers,
    )
    assert (
        requirement_detach.status_code
        == repeated_detach.status_code
        == control_detach.status_code
        == 204
    )
    actions = [
        event["action_code"]
        for event in client.get(
            f"/api/v1/requirements/{requirement['id']}/activity"
        ).json()["data"]
    ]
    assert actions.count("DOCUMENT_MAPPED") == 1
    assert actions.count("DOCUMENT_UNMAPPED") == 1
