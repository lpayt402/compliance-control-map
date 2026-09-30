from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.api.test_requirements import _by_external_id, _csrf_headers


def test_dashboard_surfaces_explainable_counts_and_action_queues(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    headers = _csrf_headers(client)
    for external_id, status, due_date in (
        ("CC6.1", "READY", None),
        ("CC6.2", "PARTIAL", None),
        ("CC7.1", "GAP", (date.today() - timedelta(days=1)).isoformat()),
    ):
        requirement = _by_external_id(client, external_id)
        response = client.patch(
            f"/api/v1/requirements/{requirement['id']}/assessment",
            headers=headers,
            json={"status_code": status, "due_date": due_date, "revision": 1},
        )
        assert response.status_code == 200

    response = client.get("/api/v1/dashboard")

    assert response.status_code == 200
    dashboard = response.json()["data"]
    assert dashboard["counts"]["READY"] == 1
    assert dashboard["counts"]["PARTIAL"] == 1
    assert dashboard["counts"]["GAP"] == 1
    assert dashboard["denominator"] == 61
    assert dashboard["readiness_percentage"] == 2
    assert dashboard["formula"] == "READY / (ALL - NOT_APPLICABLE)"
    assert dashboard["gaps"][0]["external_id"] == "CC7.1"
    assert dashboard["overdue"][0]["external_id"] == "CC7.1"
    assert dashboard["missing_documentation_count"] == 61
    assert dashboard["missing_evidence_count"] == 61
