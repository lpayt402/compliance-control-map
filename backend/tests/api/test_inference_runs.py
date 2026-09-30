import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import DatabaseManager
from app.inference.models import InferenceEvent, InferenceRequest, ProviderCapabilities
from app.models import ActivityEvent, FrameworkRequirement, InferenceRun

ORIGIN = "http://testserver"


class FakeGateway:
    def __init__(self, text: str, *, delay: float = 0) -> None:
        self._text = text
        self._delay = delay

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(streaming=True, structured_output=True)

    async def stream(
        self,
        request: InferenceRequest,
        *,
        tool_handlers=None,
    ) -> AsyncIterator[InferenceEvent]:
        if self._delay:
            import asyncio

            await asyncio.sleep(self._delay)
        midpoint = len(self._text) // 2
        yield InferenceEvent(type="text_delta", text=self._text[:midpoint])
        yield InferenceEvent(type="text_delta", text=self._text[midpoint:])
        yield InferenceEvent(
            type="usage",
            usage={"requests": 1, "tool_calls": 0, "input_tokens": 12, "output_tokens": 4},
        )
        yield InferenceEvent(type="completed")


def _headers(client: TestClient) -> dict[str, str]:
    token = client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]
    return {"Origin": ORIGIN, "X-CSRF-Token": token}


def _provider(client: TestClient, *, structured: bool = True) -> dict[str, object]:
    response = client.post(
        "/api/v1/inference/providers",
        headers=_headers(client),
        json={
            "provider_identifier": "fake-provider",
            "display_name": "Deterministic fake",
            "base_url": "http://127.0.0.1:11434/v1",
            "model_id": "fake-model",
            "capabilities": {
                "streaming": True,
                "tool_calls": False,
                "structured_output": structured,
                "embeddings": False,
            },
            "timeout_seconds": 30,
            "tls_policy": "PLAINTEXT_LOCAL_ONLY",
            "data_policy": "LOCAL_ONLY",
            "enabled": True,
            "is_default": True,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def _selection(manager: DatabaseManager) -> tuple[UUID, str]:
    with manager.session() as session:
        requirement = session.scalar(
            select(FrameworkRequirement).where(FrameworkRequirement.external_id == "CC8.1")
        )
        assert requirement is not None
        return requirement.id, requirement.external_id


def _preview(client: TestClient, requirement_id: UUID, skill_id: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/inference/context-preview",
        headers=_headers(client),
        json={
            "skill_id": skill_id,
            "record_references": [
                {"kind": "requirement", "record_id": str(requirement_id)}
            ],
            "instruction": "Draft from selected facts only.",
            "include_text_resources": True,
            "include_mapped_resources": True,
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def _run_body(
    provider: dict[str, object],
    requirement_id: UUID,
    skill_id: str,
    preview: dict[str, object],
) -> dict[str, object]:
    return {
        "provider_profile_id": provider["id"],
        "agent_id": "compliance-assistant",
        "skill_id": skill_id,
        "record_references": [{"kind": "requirement", "record_id": str(requirement_id)}],
        "instruction": "Draft from selected facts only.",
        "include_text_resources": True,
        "include_mapped_resources": True,
        "context_digest": preview["digest"],
        "external_transfer_confirmed": False,
    }


def test_run_streams_validated_proposal_then_records_history_and_feedback(
    inference_client: tuple[TestClient, DatabaseManager],
) -> None:
    client, manager = inference_client
    provider = _provider(client)
    requirement_id, external_id = _selection(manager)
    skill_id = "draft-implementation-notes"
    preview = _preview(client, requirement_id, skill_id)
    proposal = json.dumps(
        {
            "implementation_notes": "Changes are reviewed before deployment.",
            "assumptions": [],
            "missing_details": ["Confirm reviewer evidence."],
            "source_references": [f"requirement:{external_id}"],
        }
    )
    client.app.state.inference_gateway_factory = lambda *_args: FakeGateway(proposal)

    response = client.post(
        "/api/v1/inference/runs/stream",
        headers=_headers(client),
        json=_run_body(provider, requirement_id, skill_id, preview),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = [json.loads(line) for line in response.text.splitlines()]
    assert [event["type"] for event in events] == [
        "run_started",
        "status",
        "text_delta",
        "text_delta",
        "usage",
        "proposal",
        "completed",
    ]
    assert events[-1]["terminal_state"] == "COMPLETED"
    run_id = events[0]["run_id"]
    history = client.get("/api/v1/inference/runs")
    assert history.status_code == 200
    assert history.json()["data"][0]["id"] == run_id
    assert history.json()["data"][0]["structured_result"]["implementation_notes"].startswith(
        "Changes"
    )
    assert history.json()["data"][0]["usage_metrics"] == {
        "requests": 1,
        "tool_calls": 0,
        "input_tokens": 12,
        "output_tokens": 4,
    }

    feedback = client.post(
        f"/api/v1/inference/runs/{run_id}/feedback",
        headers=_headers(client),
        json={"rating": "USEFUL", "comment": "Good starting point."},
    )
    assert feedback.status_code == 200
    assert feedback.json()["data"]["feedback_rating"] == "USEFUL"
    with manager.session() as session:
        run = session.get(InferenceRun, UUID(run_id))
        assert run is not None and run.status == "COMPLETED"
        events = list(
            session.scalars(
                select(ActivityEvent).where(ActivityEvent.entity_type == "INFERENCE_RUN")
            )
        )
        assert [event.action_code for event in events] == [
            "MODEL_RUN_STARTED",
            "MODEL_RUN_COMPLETED",
            "MODEL_RUN_FEEDBACK_RECORDED",
        ]
        activity_text = repr([(event.before_snapshot, event.after_snapshot) for event in events])
        assert "Draft from selected facts" not in activity_text
        assert "Changes are reviewed" not in activity_text


def test_changed_context_digest_is_rejected_before_provider_call(
    inference_client: tuple[TestClient, DatabaseManager],
) -> None:
    client, manager = inference_client
    provider = _provider(client)
    requirement_id, _external_id = _selection(manager)
    skill_id = "requirement-summary-next-actions"
    preview = _preview(client, requirement_id, skill_id)
    body = _run_body(provider, requirement_id, skill_id, preview)
    body["context_digest"] = "0" * 64
    called = False

    def factory(*_args):
        nonlocal called
        called = True
        return FakeGateway("unused")

    client.app.state.inference_gateway_factory = factory
    response = client.post(
        "/api/v1/inference/runs/stream",
        headers=_headers(client),
        json=body,
    )

    assert response.status_code == 409
    assert called is False


def test_unstructured_provider_falls_back_to_advice_only_text(
    inference_client: tuple[TestClient, DatabaseManager],
) -> None:
    client, manager = inference_client
    provider = _provider(client, structured=False)
    requirement_id, _external_id = _selection(manager)
    skill_id = "draft-implementation-notes"
    preview = _preview(client, requirement_id, skill_id)
    client.app.state.inference_gateway_factory = lambda *_args: FakeGateway("Plain advice")

    response = client.post(
        "/api/v1/inference/runs/stream",
        headers=_headers(client),
        json=_run_body(provider, requirement_id, skill_id, preview),
    )
    events = [json.loads(line) for line in response.text.splitlines()]

    assert response.status_code == 200
    assert not any(event["type"] == "proposal" for event in events)
    assert events[-1] == {
        "type": "completed",
        "terminal_state": "COMPLETED",
        "structured": False,
    }


def test_run_timeout_has_finite_terminal_state(
    inference_client: tuple[TestClient, DatabaseManager],
) -> None:
    client, manager = inference_client
    provider = _provider(client, structured=False)
    requirement_id, _external_id = _selection(manager)
    skill_id = "requirement-summary-next-actions"
    preview = _preview(client, requirement_id, skill_id)
    client.app.state.settings.inference_timeout_seconds = 1
    client.app.state.inference_gateway_factory = lambda *_args: FakeGateway("late", delay=1.1)

    response = client.post(
        "/api/v1/inference/runs/stream",
        headers=_headers(client),
        json=_run_body(provider, requirement_id, skill_id, preview),
    )
    events = [json.loads(line) for line in response.text.splitlines()]

    assert events[-1]["type"] == "error"
    assert events[-1]["terminal_state"] == "TIMED_OUT"
    assert events[-1]["error_code"] == "RUN_TIMEOUT"


def test_run_output_limit_has_finite_failed_state(
    inference_client: tuple[TestClient, DatabaseManager],
) -> None:
    client, manager = inference_client
    provider = _provider(client, structured=False)
    requirement_id, _external_id = _selection(manager)
    skill_id = "requirement-summary-next-actions"
    preview = _preview(client, requirement_id, skill_id)
    client.app.state.settings.inference_max_output_chars = 5
    client.app.state.inference_gateway_factory = lambda *_args: FakeGateway(
        "provider output is too long"
    )

    response = client.post(
        "/api/v1/inference/runs/stream",
        headers=_headers(client),
        json=_run_body(provider, requirement_id, skill_id, preview),
    )
    events = [json.loads(line) for line in response.text.splitlines()]

    assert events[-1]["type"] == "error"
    assert events[-1]["terminal_state"] == "FAILED"
    assert events[-1]["error_code"] == "OUTPUT_LIMIT"


def test_external_provider_requires_fresh_confirmation(
    inference_client: tuple[TestClient, DatabaseManager],
) -> None:
    client, manager = inference_client
    client.app.state.settings.inference_allowed_base_urls = ["https://models.example.com/v1"]
    response = client.post(
        "/api/v1/inference/providers",
        headers=_headers(client),
        json={
            "provider_identifier": "external",
            "display_name": "External provider",
            "base_url": "https://models.example.com/v1",
            "model_id": "hosted-model",
            "capabilities": {"streaming": True},
            "tls_policy": "REQUIRED",
            "data_policy": "REDACTED_EXTERNAL",
            "enabled": True,
            "is_default": True,
        },
    )
    assert response.status_code == 201
    provider = response.json()["data"]
    requirement_id, _external_id = _selection(manager)
    skill_id = "requirement-summary-next-actions"
    preview = _preview(client, requirement_id, skill_id)
    body = _run_body(provider, requirement_id, skill_id, preview)

    denied = client.post(
        "/api/v1/inference/runs/stream",
        headers=_headers(client),
        json=body,
    )

    assert denied.status_code == 422
    assert "confirmation" in denied.text.casefold()
