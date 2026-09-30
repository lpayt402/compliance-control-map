from fastapi.testclient import TestClient

from tests.api.test_requirements import _by_external_id, _csrf_headers


def _create_control(client: TestClient, code: str = "AC-01") -> dict[str, object]:
    response = client.post(
        "/api/v1/controls",
        headers=_csrf_headers(client),
        json={
            "code": code,
            "name": "Access review",
            "description": "Review logical access on a defined cadence.",
            "status_code": "OPERATING",
            "implementation_notes": "Quarterly review owned by Security.",
            "tags": ["access", "detective"],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_control_crud_and_many_to_many_requirement_mapping(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    control = _create_control(client)
    cc61 = _by_external_id(client, "CC6.1")
    cc62 = _by_external_id(client, "CC6.2")
    headers = _csrf_headers(client)

    for requirement, coverage in ((cc61, "PRIMARY"), (cc62, "SUPPORTING")):
        mapped = client.post(
            f"/api/v1/requirements/{requirement['id']}/controls",
            headers=headers,
            json={
                "control_id": control["id"],
                "coverage": coverage,
                "rationale": "Shared identity governance process.",
            },
        )
        assert mapped.status_code == 201

    detail = client.get(f"/api/v1/controls/{control['id']}").json()["data"]
    req_detail = client.get(f"/api/v1/requirements/{cc61['id']}").json()["data"]
    assert detail["status_code"] == "OPERATING"
    assert detail["tags"] == ["access", "detective"]
    assert {item["requirement"]["external_id"] for item in detail["requirements"]} == {
        "CC6.1",
        "CC6.2",
    }
    assert req_detail["assessment"]["status_code"] == "NOT_ASSESSED"
    assert req_detail["control_count"] == 1

    changed = client.patch(
        f"/api/v1/controls/{control['id']}",
        headers=headers,
        json={"name": "Quarterly access review", "revision": 1},
    )
    assert changed.status_code == 200
    assert changed.json()["data"]["revision"] == 2


def test_multiple_controls_can_support_one_requirement_and_links_can_be_removed(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    first = _create_control(client, "AC-01")
    second = _create_control(client, "AC-02")
    requirement = _by_external_id(client, "CC6.1")
    headers = _csrf_headers(client)
    for control in (first, second):
        response = client.post(
            f"/api/v1/requirements/{requirement['id']}/controls",
            headers=headers,
            json={"control_id": control["id"], "coverage": "SUPPORTING", "rationale": ""},
        )
        assert response.status_code == 201

    mappings = client.get(f"/api/v1/requirements/{requirement['id']}/controls").json()[
        "data"
    ]
    removed = client.delete(
        f"/api/v1/requirements/{requirement['id']}/controls/{first['id']}",
        headers=headers,
    )
    assert len(mappings) == 2
    assert removed.status_code == 204
    assert len(
        client.get(f"/api/v1/requirements/{requirement['id']}/controls").json()["data"]
    ) == 1


def test_control_resources_have_the_same_typed_lifecycle(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    control = _create_control(client)
    headers = _csrf_headers(client)

    created = client.post(
        f"/api/v1/controls/{control['id']}/notes",
        headers=headers,
        json={
            "kind": "PLAYBOOK",
            "title": "Quarterly access review",
            "body": "Export users, obtain manager approval, and retain the signed report.",
        },
    )
    assert created.status_code == 201
    resource = created.json()["data"]
    assert resource["revision"] == 1

    changed = client.patch(
        f"/api/v1/controls/{control['id']}/notes/{resource['id']}",
        headers=headers,
        json={"revision": 1, "title": "Monthly access review"},
    )
    assert changed.status_code == 200
    assert changed.json()["data"]["revision"] == 2

    listed = client.get(f"/api/v1/controls/{control['id']}/notes")
    assert listed.status_code == 200
    assert listed.json()["data"][0]["title"] == "Monthly access review"

    removed = client.delete(
        f"/api/v1/controls/{control['id']}/notes/{resource['id']}?revision=2",
        headers=headers,
    )
    assert removed.status_code == 204
    activity = client.get(f"/api/v1/controls/{control['id']}/activity").json()["data"]
    assert [event["action_code"] for event in activity[:3]] == [
        "PLAYBOOK_DELETED",
        "PLAYBOOK_UPDATED",
        "PLAYBOOK_CREATED",
    ]


def test_stale_control_edit_uses_revision_problem_contract(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    control = _create_control(client)
    response = client.patch(
        f"/api/v1/controls/{control['id']}",
        headers=_csrf_headers(client),
        json={"name": "Stale", "revision": 99},
    )
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["current"]["revision"] == 1
