from fastapi.testclient import TestClient

from tests.api.test_requirements import _by_external_id, _csrf_headers


def test_crosswalk_is_directional_and_does_not_transfer_readiness(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    source = _by_external_id(client, "CC6.1")
    target = _by_external_id(client, "CC6.2")
    headers = _csrf_headers(client)
    assert client.patch(
        f"/api/v1/requirements/{source['id']}/assessment",
        headers=headers,
        json={"status_code": "READY", "revision": 1},
    ).status_code == 200
    assert client.patch(
        f"/api/v1/requirements/{target['id']}/assessment",
        headers=headers,
        json={"status_code": "GAP", "revision": 1},
    ).status_code == 200

    created = client.post(
        "/api/v1/requirement-mappings",
        headers=headers,
        json={
            "source_requirement_id": source["id"],
            "target_requirement_id": target["id"],
            "relationship_type": "STRONG_OVERLAP",
            "confidence": 85,
            "mapping_source": "Manual review",
            "notes": "Shared access-control intent, not identical evidence expectations.",
        },
    )

    assert created.status_code == 201
    assert client.get(f"/api/v1/requirements/{target['id']}").json()["data"]["assessment"][
        "status_code"
    ] == "GAP"
    outbound = client.get(f"/api/v1/requirements/{source['id']}/mappings").json()["data"]
    inbound = client.get(f"/api/v1/requirements/{target['id']}/mappings").json()["data"]
    assert outbound[0]["direction"] == "OUTBOUND"
    assert outbound[0]["other_requirement"]["external_id"] == "CC6.2"
    assert inbound[0]["direction"] == "INBOUND"
    assert inbound[0]["other_requirement"]["external_id"] == "CC6.1"


def test_crosswalk_rejects_self_links_duplicates_and_bad_confidence(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    source = _by_external_id(client, "CC7.1")
    target = _by_external_id(client, "CC8.1")
    headers = _csrf_headers(client)
    payload = {
        "source_requirement_id": source["id"],
        "target_requirement_id": target["id"],
        "relationship_type": "PARTIAL_OVERLAP",
        "confidence": 60,
        "mapping_source": "Internal crosswalk v1",
        "notes": "Related monitoring and change signals.",
    }

    assert (
        client.post("/api/v1/requirement-mappings", headers=headers, json=payload).status_code
        == 201
    )
    assert (
        client.post("/api/v1/requirement-mappings", headers=headers, json=payload).status_code
        == 409
    )
    self_link = {**payload, "target_requirement_id": source["id"]}
    bad_confidence = {**payload, "confidence": 101, "relationship_type": "RELATED"}
    assert client.post(
        "/api/v1/requirement-mappings", headers=headers, json=self_link
    ).status_code == 422
    assert client.post(
        "/api/v1/requirement-mappings", headers=headers, json=bad_confidence
    ).status_code == 422
