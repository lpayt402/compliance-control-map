from fastapi.testclient import TestClient

from app.main import create_app


def test_liveness_returns_stable_envelope() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}, "meta": {}}
