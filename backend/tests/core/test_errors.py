from fastapi.testclient import TestClient

from app.main import create_app


def test_unhandled_errors_return_safe_problem_with_request_id() -> None:
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("database password is swordfish")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["x-request-id"] == response.json()["request_id"]
    assert "swordfish" not in response.text
