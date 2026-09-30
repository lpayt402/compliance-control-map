from collections.abc import AsyncIterator, Awaitable, Callable, Mapping

import httpx2
from pydantic_ai import Agent, Tool
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from app.inference.models import (
    InferenceEvent,
    InferenceRequest,
    ProviderCapabilities,
    ProviderConnection,
    StructuredProposal,
)

ToolHandler = Callable[..., Awaitable[str]]


async def run_structured_proof(model: Model, prompt: str) -> StructuredProposal:
    """Exercise Pydantic AI's validated structured-output path."""

    agent = Agent(model, output_type=StructuredProposal)
    result = await agent.run(prompt)
    return result.output


class OpenAICompatibleGateway:
    """Minimal provider adapter used to prove streaming and read-only tools."""

    def __init__(self, connection: ProviderConnection, *, api_key: str | None) -> None:
        self._connection = connection
        self._api_key = api_key

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._connection.capabilities

    async def stream(
        self,
        request: InferenceRequest,
        *,
        tool_handlers: Mapping[str, ToolHandler] | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        http_client = httpx2.AsyncClient(
            trust_env=False,
            follow_redirects=False,
            timeout=self._connection.timeout_seconds,
            limits=httpx2.Limits(max_connections=1, max_keepalive_connections=1),
        )
        try:
            provider = OpenAIProvider(
                base_url=str(self._connection.base_url),
                api_key=self._api_key,
                http_client=http_client,
            )
            model = OpenAIChatModel(self._connection.model_id, provider=provider)
            tools = [
                Tool(handler, name=tool_id, sequential=True)
                for tool_id, handler in (tool_handlers or {}).items()
                if tool_id in request.tool_ids
            ]
            agent = Agent(model, tools=tools)
            prompt = "\n\n".join(
                f"{message.role.upper()}: {message.content}" for message in request.messages
            )
            async with agent.run_stream(
                prompt,
                usage_limits=UsageLimits(
                    request_limit=request.max_iterations,
                    tool_calls_limit=request.max_tool_calls,
                ),
            ) as result:
                async for delta in result.stream_text(delta=True):
                    if delta:
                        yield InferenceEvent(type="text_delta", text=delta)
                usage = result.usage
            yield InferenceEvent(
                type="usage",
                usage={
                    "requests": usage.requests,
                    "tool_calls": usage.tool_calls,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cache_write_tokens": usage.cache_write_tokens,
                    "cache_read_tokens": usage.cache_read_tokens,
                },
            )
            yield InferenceEvent(type="completed")
        finally:
            await http_client.aclose()
