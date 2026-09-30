import json
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import ClassVar

import pytest
from pydantic_ai.models.test import TestModel

from app.inference.models import (
    DataPolicy,
    InferenceMessage,
    InferenceRequest,
    ProviderCapabilities,
    ProviderConnection,
    StructuredProposal,
    TLSPolicy,
)
from app.inference.openai_compatible import OpenAICompatibleGateway, run_structured_proof


class _ChatCompletionsHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    request_bodies: ClassVar[list[dict[str, object]]] = []

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_POST(self) -> None:
        assert self.path == "/v1/chat/completions"
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        assert isinstance(body, dict)
        self.request_bodies.append(body)
        messages = body.get("messages")
        assert isinstance(messages, list)
        has_tool_return = any(
            isinstance(message, dict) and message.get("role") == "tool" for message in messages
        )

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        chunks = self._answer_chunks() if has_tool_return else self._tool_chunks()
        for chunk in chunks:
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True

    @staticmethod
    def _tool_chunks() -> list[dict[str, object]]:
        return [
            {
                "id": "chatcmpl-tool",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "proof-model",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call-proof",
                                    "type": "function",
                                    "function": {
                                        "name": "read_selected_context",
                                        "arguments": '{"source_ref":"requirement:CC8.1"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chatcmpl-tool",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "proof-model",
                "choices": [
                    {"index": 0, "delta": {}, "finish_reason": "tool_calls"}
                ],
            },
        ]

    @staticmethod
    def _answer_chunks() -> list[dict[str, object]]:
        return [
            {
                "id": "chatcmpl-answer",
                "object": "chat.completion.chunk",
                "created": 2,
                "model": "proof-model",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": "Grounded "},
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chatcmpl-answer",
                "object": "chat.completion.chunk",
                "created": 2,
                "model": "proof-model",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": "proposal."},
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chatcmpl-answer",
                "object": "chat.completion.chunk",
                "created": 2,
                "model": "proof-model",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            },
        ]


@pytest.fixture
def fake_chat_server() -> Generator[tuple[str, type[_ChatCompletionsHandler]], None, None]:
    _ChatCompletionsHandler.request_bodies = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ChatCompletionsHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/v1", _ChatCompletionsHandler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.anyio
async def test_deterministic_agent_returns_validated_structured_proposal() -> None:
    model = TestModel(
        custom_output_args={
            "summary": "Current state is documented.",
            "source_references": ["requirement:CC8.1"],
            "limitations": ["No attachment bytes were reviewed."],
        }
    )

    proposal = await run_structured_proof(model, "Summarize the selected requirement.")

    assert proposal == StructuredProposal(
        summary="Current state is documented.",
        source_references=("requirement:CC8.1",),
        limitations=("No attachment bytes were reviewed.",),
    )


@pytest.mark.anyio
async def test_fake_chat_server_streams_text_and_one_read_only_tool_call(
    fake_chat_server: tuple[str, type[_ChatCompletionsHandler]],
) -> None:
    base_url, handler = fake_chat_server
    connection = ProviderConnection(
        provider_id="proof-provider",
        base_url=base_url,
        model_id="proof-model",
        capabilities=ProviderCapabilities(streaming=True, tool_calls=True),
        timeout_seconds=10,
        tls_policy=TLSPolicy.PLAINTEXT_LOCAL_ONLY,
        data_policy=DataPolicy.LOCAL_ONLY,
    )
    gateway = OpenAICompatibleGateway(connection, api_key="not-needed")
    tool_calls: list[str] = []

    async def read_selected_context(source_ref: str) -> str:
        tool_calls.append(source_ref)
        return "CC8.1 has one mapped control."

    request = InferenceRequest(
        messages=(InferenceMessage(role="user", content="Review the selected requirement."),),
        tool_ids=("read_selected_context",),
    )

    events = [
        event
        async for event in gateway.stream(
            request,
            tool_handlers={"read_selected_context": read_selected_context},
        )
    ]

    assert tool_calls == ["requirement:CC8.1"]
    assert "".join(event.text or "" for event in events if event.type == "text_delta") == (
        "Grounded proposal."
    )
    assert events[-1].type == "completed"
    usage_event = next(event for event in events if event.type == "usage")
    assert usage_event.usage is not None
    assert usage_event.usage["requests"] == 2
    assert usage_event.usage["tool_calls"] == 1
    assert len(handler.request_bodies) == 2
    second_messages = handler.request_bodies[1]["messages"]
    assert isinstance(second_messages, list)
    assert any(
        isinstance(message, dict) and message.get("role") == "tool"
        for message in second_messages
    )
