import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import DatabaseManager
from app.inference.models import InferenceEvent, InferenceRequest, ProviderCapabilities
from app.models import ActivityEvent, InferenceProviderProfile, Workspace

ORIGIN = "http://testserver"


class _ProviderTestGateway:
    def __init__(self, *, fail: bool = False, delay: float = 0) -> None:
        self._fail = fail
        self._delay = delay

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(streaming=True)

    async def stream(
        self,
        request: InferenceRequest,
        *,
        tool_handlers=None,
    ) -> AsyncIterator[InferenceEvent]:
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._fail:
            raise RuntimeError("raw-provider-body-with-sensitive-details")
        yield InferenceEvent(type="text_delta", text="OK")
        yield InferenceEvent(type="completed")


def _headers(client: TestClient) -> dict[str, str]:
    token = client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]
    return {"Origin": ORIGIN, "X-CSRF-Token": token}


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "provider_identifier": "local-ollama",
        "display_name": "Local Ollama",
        "base_url": "http://127.0.0.1:11434/v1/",
        "model_id": "qwen3:8b",
        "api_mode": "CHAT_COMPLETIONS",
        "capabilities": {
            "streaming": True,
            "tool_calls": True,
            "structured_output": False,
            "embeddings": False,
            "max_context_tokens": 32_000,
        },
        "timeout_seconds": 60,
        "tls_policy": "PLAINTEXT_LOCAL_ONLY",
        "data_policy": "LOCAL_ONLY",
        "secret_ref": None,
        "enabled": True,
        "is_default": True,
    }
    payload.update(overrides)
    return payload


def test_status_and_skills_expose_bounded_non_secret_configuration(
    inference_client: tuple[TestClient, DatabaseManager],
) -> None:
    client, _manager = inference_client

    status = client.get("/api/v1/inference/status")
    skills = client.get("/api/v1/inference/skills")

    assert status.status_code == 200
    assert status.json()["data"] == {
        "enabled": True,
        "ready": True,
        "allowed_base_urls": ["http://127.0.0.1:11434/v1"],
        "limits": {
            "max_concurrent_runs": 2,
            "max_context_chars": 60000,
            "max_output_chars": 12000,
            "max_iterations": 4,
            "max_tool_calls": 8,
            "timeout_seconds": 90,
        },
    }
    assert len(skills.json()["data"]) == 4
    assert all(item["writes_workspace"] is False for item in skills.json()["data"])


def test_admin_can_create_patch_list_and_delete_non_secret_provider(
    inference_client: tuple[TestClient, DatabaseManager],
) -> None:
    client, manager = inference_client
    headers = _headers(client)

    created = client.post("/api/v1/inference/providers", headers=headers, json=_payload())

    assert created.status_code == 201
    profile = created.json()["data"]
    assert profile["base_url"] == "http://127.0.0.1:11434/v1"
    assert profile["secret_status"] == "NOT_REQUIRED"  # noqa: S105 - enum state
    assert "secret_ref" not in profile
    assert "api_key" not in profile
    listed = client.get("/api/v1/inference/providers")
    assert listed.json()["data"] == [profile]

    patched = client.patch(
        f"/api/v1/inference/providers/{profile['id']}",
        headers=headers,
        json={"revision": profile["revision"], "display_name": "On-device Ollama"},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["display_name"] == "On-device Ollama"
    assert patched.json()["data"]["revision"] == 2

    stale = client.patch(
        f"/api/v1/inference/providers/{profile['id']}",
        headers=headers,
        json={"revision": 1, "display_name": "Stale"},
    )
    assert stale.status_code == 409

    deleted = client.delete(f"/api/v1/inference/providers/{profile['id']}", headers=headers)
    assert deleted.status_code == 204
    with manager.session() as session:
        events = list(
            session.scalars(
                select(ActivityEvent).where(ActivityEvent.entity_type == "INFERENCE_PROVIDER")
            )
        )
        assert [event.action_code for event in events] == [
            "PROVIDER_CREATED",
            "PROVIDER_UPDATED",
            "PROVIDER_DELETED",
        ]
        serialized = repr([(event.before_snapshot, event.after_snapshot) for event in events])
        assert "secret" not in serialized.casefold()
        assert "api_key" not in serialized.casefold()


def test_provider_schema_rejects_key_values_and_reports_env_reference_status(
    inference_client: tuple[TestClient, DatabaseManager],
    monkeypatch,
) -> None:
    client, _manager = inference_client
    headers = _headers(client)
    leaked = client.post(
        "/api/v1/inference/providers",
        headers=headers,
        json=_payload(api_key="must-not-enter-api"),
    )
    assert leaked.status_code == 422
    assert "must-not-enter-api" not in leaked.text

    missing = client.post(
        "/api/v1/inference/providers",
        headers=headers,
        json=_payload(
            provider_identifier="hosted",
            secret_ref="env:CCM_TEST_PROVIDER_KEY",  # noqa: S106 - reference only
            enabled=False,
            is_default=False,
        ),
    )
    assert missing.status_code == 201
    assert missing.json()["data"]["secret_status"] == "MISSING"  # noqa: S105 - enum state

    monkeypatch.setenv("CCM_TEST_PROVIDER_KEY", "top-secret-provider-value")
    listed = client.get("/api/v1/inference/providers")
    hosted = next(item for item in listed.json()["data"] if item["provider_identifier"] == "hosted")
    assert hosted["secret_status"] == "CONFIGURED"  # noqa: S105 - enum state
    assert "top-secret-provider-value" not in listed.text


def test_provider_object_lookups_are_workspace_scoped(
    inference_client: tuple[TestClient, DatabaseManager],
) -> None:
    client, manager = inference_client
    with manager.session() as session:
        other_workspace = Workspace(slug="other", name="Other", timezone="UTC", locale="en-US")
        session.add(other_workspace)
        session.flush()
        foreign = InferenceProviderProfile(
            workspace_id=other_workspace.id,
            provider_identifier="foreign",
            display_name="Foreign",
            base_url="http://127.0.0.1:11434/v1",
            model_id="foreign",
            api_mode="CHAT_COMPLETIONS",
            capabilities={},
            timeout_seconds=30,
            tls_policy="PLAINTEXT_LOCAL_ONLY",
            data_policy="LOCAL_ONLY",
            enabled=False,
            is_default=False,
        )
        session.add(foreign)
        session.flush()
        foreign_id = foreign.id

    response = client.patch(
        f"/api/v1/inference/providers/{foreign_id}",
        headers=_headers(client),
        json={"revision": 1, "display_name": "Forged"},
    )

    assert response.status_code == 404


def test_provider_identifier_is_unique_per_workspace(
    inference_client: tuple[TestClient, DatabaseManager],
) -> None:
    client, _manager = inference_client
    headers = _headers(client)
    created = client.post("/api/v1/inference/providers", headers=headers, json=_payload())
    assert created.status_code == 201
    duplicate = client.post("/api/v1/inference/providers", headers=headers, json=_payload())
    assert duplicate.status_code == 409


def test_unknown_provider_id_is_not_distinguished_from_cross_workspace_id(
    inference_client: tuple[TestClient, DatabaseManager],
) -> None:
    client, _manager = inference_client
    response = client.delete(f"/api/v1/inference/providers/{uuid4()}", headers=_headers(client))
    assert response.status_code == 404


def test_admin_provider_test_reports_sanitized_success_and_failure(
    inference_client: tuple[TestClient, DatabaseManager],
) -> None:
    client, manager = inference_client
    created = client.post(
        "/api/v1/inference/providers",
        headers=_headers(client),
        json=_payload(enabled=False, is_default=False),
    ).json()["data"]
    client.app.state.inference_gateway_factory = lambda *_args: _ProviderTestGateway()

    success = client.post(
        f"/api/v1/inference/providers/{created['id']}/test",
        headers=_headers(client),
    )

    assert success.status_code == 200
    assert success.json()["data"]["reachable"] is True
    assert success.json()["data"]["model_accepted"] is True
    assert success.json()["data"]["error_code"] is None
    assert "OK" not in success.text

    client.app.state.inference_gateway_factory = lambda *_args: _ProviderTestGateway(fail=True)
    failed = client.post(
        f"/api/v1/inference/providers/{created['id']}/test",
        headers=_headers(client),
    )
    assert failed.status_code == 200
    assert failed.json()["data"]["reachable"] is False
    assert failed.json()["data"]["error_code"] == "PROVIDER_UNREACHABLE"
    assert "raw-provider-body" not in failed.text
    with manager.session() as session:
        events = list(
            session.scalars(
                select(ActivityEvent).where(
                    ActivityEvent.entity_type == "INFERENCE_PROVIDER",
                    ActivityEvent.action_code == "PROVIDER_TESTED",
                )
            )
        )
        assert [event.after_snapshot["outcome"] for event in events] == [
            "REACHABLE",
            "UNREACHABLE",
        ]
        assert "raw-provider-body" not in repr(events)


def test_provider_test_timeout_is_sanitized(
    inference_client: tuple[TestClient, DatabaseManager],
) -> None:
    client, _manager = inference_client
    created = client.post(
        "/api/v1/inference/providers",
        headers=_headers(client),
        json=_payload(enabled=False, is_default=False),
    ).json()["data"]
    client.app.state.settings.inference_timeout_seconds = 1
    client.app.state.inference_gateway_factory = lambda *_args: _ProviderTestGateway(
        delay=1.1
    )

    response = client.post(
        f"/api/v1/inference/providers/{created['id']}/test",
        headers=_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["data"]["reachable"] is False
    assert response.json()["data"]["error_code"] == "PROVIDER_TIMEOUT"
    assert response.json()["data"]["message"] == "The provider test timed out."
