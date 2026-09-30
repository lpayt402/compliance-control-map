from fastapi.testclient import TestClient

from tests.api.test_controls import _create_control
from tests.api.test_requirements import _by_external_id, _csrf_headers


def test_evidence_reuses_one_artifact_across_requirements_and_controls(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    requirement = _by_external_id(client, "CC6.1")
    control = _create_control(client)
    response = client.post(
        "/api/v1/evidence",
        headers=_csrf_headers(client),
        data={
            "name": "Quarterly access review",
            "description": "Q2 reviewer sign-off.",
            "requirement_ids": [requirement["id"]],
            "control_ids": [control["id"]],
        },
        files={"file": ("access-review.csv", b"user,result\nalice,approved\n", "text/csv")},
    )

    assert response.status_code == 201
    evidence = response.json()["data"]
    assert evidence["requirements"][0]["external_id"] == "CC6.1"
    assert evidence["controls"][0]["code"] == "AC-01"
    by_requirement = client.get(
        f"/api/v1/requirements/{requirement['id']}/evidence"
    ).json()["data"]
    assert by_requirement[0]["id"] == evidence["id"]
    assert client.get(f"/api/v1/requirements/{requirement['id']}").json()["data"][
        "evidence_count"
    ] == 1


def test_evidence_links_can_be_managed_from_requirement_and_control(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    requirement = _by_external_id(client, "CC6.2")
    control = _create_control(client)
    headers = _csrf_headers(client)
    evidence = client.post(
        "/api/v1/evidence",
        headers=headers,
        data={"name": "Review report"},
        files={"file": ("review.csv", b"user,result\nalice,approved\n", "text/csv")},
    ).json()["data"]

    assert client.post(
        f"/api/v1/requirements/{requirement['id']}/evidence",
        headers=headers,
        json={"evidence_ids": [evidence["id"]], "rationale": "Review result."},
    ).status_code == 200
    assert client.post(
        f"/api/v1/controls/{control['id']}/evidence",
        headers=headers,
        json={"evidence_ids": [evidence["id"]]},
    ).status_code == 200
    assert client.get(f"/api/v1/controls/{control['id']}/evidence").json()["data"][0][
        "id"
    ] == evidence["id"]

    assert client.delete(
        f"/api/v1/requirements/{requirement['id']}/evidence/{evidence['id']}",
        headers=headers,
    ).status_code == 204
    assert client.delete(
        f"/api/v1/controls/{control['id']}/evidence/{evidence['id']}",
        headers=headers,
    ).status_code == 204
