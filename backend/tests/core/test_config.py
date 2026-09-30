from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_local_defaults_are_loopback_and_sqlite(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, storage_root=tmp_path / "files")

    assert settings.bind_host == "127.0.0.1"
    assert settings.database_url.startswith("sqlite:///")
    assert settings.auth_mode == "disabled"
    assert settings.inference_enabled is False
    assert settings.inference_allowed_base_urls == []
    assert settings.inference_max_concurrent_runs == 2
    assert settings.inference_max_context_chars == 60_000
    assert settings.inference_max_output_chars == 12_000
    assert settings.inference_max_iterations == 4
    assert settings.inference_max_tool_calls == 8
    assert settings.inference_timeout_seconds == 90


def test_disabled_auth_rejects_remote_bind(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="only bind to loopback"):
        Settings(
            bind_host="0.0.0.0",  # noqa: S104 - this is the value under test
            data_dir=tmp_path,
            storage_root=tmp_path / "files",
        )


def test_production_rejects_example_secrets(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="CHANGE_ME"):
        Settings(
            app_env="production",
            auth_mode="local",
            bind_host="0.0.0.0",  # noqa: S104 - production bind is under test
            database_url=(
                "postgresql+psycopg://ccm:CHANGE_ME_database@postgres:5432/compliance_control"
            ),
            bootstrap_admin_email="admin@example.com",
            bootstrap_admin_password="CHANGE_ME_admin_password",  # noqa: S106
            data_dir=tmp_path,
            storage_root=tmp_path / "files",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("inference_max_concurrent_runs", 9),
        ("inference_max_context_chars", 600_001),
        ("inference_max_output_chars", 120_001),
        ("inference_max_iterations", 9),
        ("inference_max_tool_calls", 33),
        ("inference_timeout_seconds", 301),
    ],
)
def test_inference_limits_have_server_side_safe_bounds(
    tmp_path: Path,
    field: str,
    value: int,
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            data_dir=tmp_path,
            storage_root=tmp_path / "files",
            **{field: value},
        )
