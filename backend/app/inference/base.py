from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from typing import Protocol

from app.inference.models import InferenceEvent, InferenceRequest, ProviderCapabilities


class InferenceGateway(Protocol):
    """Future adapter boundary; intentionally has no V1 implementation."""

    @property
    def capabilities(self) -> ProviderCapabilities: ...

    def stream(
        self,
        request: InferenceRequest,
        *,
        tool_handlers: Mapping[str, Callable[..., Awaitable[str]]] | None = None,
    ) -> AsyncIterator[InferenceEvent]: ...
