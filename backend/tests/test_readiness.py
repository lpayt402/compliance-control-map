from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


class BrokenDatabase:
    def is_ready(self) -> bool:
        return False


def test_readiness_fails_when_database_is_unavailable(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test",
        data_dir=tmp_path,
        storage_root=tmp_path / "files",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
    )
    client = TestClient(create_app(settings=settings, database_manager=BrokenDatabase()))

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["status"] == 503
