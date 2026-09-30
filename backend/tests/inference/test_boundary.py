import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.inference.models import (
    DataPolicy,
    ProviderCapabilities,
    ProviderConnection,
    TLSPolicy,
)


def test_provider_connection_is_explicit_and_never_accepts_a_secret_value() -> None:
    connection = ProviderConnection(
        provider_id="local-model",
        base_url="http://192.168.1.50:11434/v1",
        model_id="example-model",
        capabilities=ProviderCapabilities(streaming=True, tool_calls=False),
        timeout_seconds=45,
        tls_policy=TLSPolicy.REQUIRED,
        data_policy=DataPolicy.LOCAL_ONLY,
        secret_ref="env:CCM_INFERENCE_API_KEY",  # noqa: S106 - reference, not a secret
    )

    payload = connection.model_dump(mode="json")

    assert payload["base_url"] == "http://192.168.1.50:11434/v1"
    assert payload["secret_ref"] == "env:CCM_INFERENCE_API_KEY"  # noqa: S105
    assert "secret" not in payload
    assert "api_key" not in payload

    with pytest.raises(ValidationError):
        ProviderConnection.model_validate({**payload, "secret_value": "do-not-store-me"})


def test_provider_sdk_imports_are_isolated_inside_inference_boundary() -> None:
    app_root = Path(__file__).parents[2] / "app"
    forbidden_roots = {"anthropic", "google.generativeai", "groq", "openai"}
    imported: set[str] = set()

    violations: set[str] = set()
    for source_path in app_root.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        provider_imports = {
            name
            for name in imported
            if any(name == root or name.startswith(f"{root}.") for root in forbidden_roots)
        }
        if provider_imports and source_path.parent.name != "inference":
            violations.add(str(source_path.relative_to(app_root)))

    assert violations == set()


def test_inference_routes_remain_safe_and_empty_when_kill_switch_is_off(
    requirements_client,
) -> None:
    status = requirements_client.get("/api/v1/inference/status")
    providers = requirements_client.get("/api/v1/inference/providers")

    assert status.status_code == 200
    assert status.json()["data"]["enabled"] is False
    assert status.json()["data"]["ready"] is False
    assert providers.status_code == 200
    assert providers.json()["data"] == []
