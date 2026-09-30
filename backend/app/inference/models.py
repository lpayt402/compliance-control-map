from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class BoundaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TLSPolicy(StrEnum):
    REQUIRED = "REQUIRED"
    PRIVATE_CA_ALLOWED = "PRIVATE_CA_ALLOWED"
    PLAINTEXT_LOCAL_ONLY = "PLAINTEXT_LOCAL_ONLY"


class DataPolicy(StrEnum):
    LOCAL_ONLY = "LOCAL_ONLY"
    REDACTED_EXTERNAL = "REDACTED_EXTERNAL"
    EXTERNAL_ALLOWED = "EXTERNAL_ALLOWED"


class ProviderCapabilities(BoundaryModel):
    streaming: bool = True
    tool_calls: bool = False
    structured_output: bool = False
    embeddings: bool = False
    max_context_tokens: int | None = Field(default=None, ge=1)


class ProviderConnection(BoundaryModel):
    """Non-secret connection metadata for a future provider adapter."""

    provider_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    base_url: AnyHttpUrl
    model_id: str = Field(min_length=1, max_length=200)
    capabilities: ProviderCapabilities
    timeout_seconds: int = Field(default=60, ge=1, le=300)
    tls_policy: TLSPolicy = TLSPolicy.REQUIRED
    data_policy: DataPolicy = DataPolicy.LOCAL_ONLY
    secret_ref: str | None = Field(
        default=None,
        max_length=240,
        pattern=r"^env:[A-Z][A-Z0-9_]*$",
        description="Reference to an external secret; never the credential value.",
    )


class RecordReference(BoundaryModel):
    kind: Literal["requirement", "control", "document", "evidence"]
    record_id: UUID


class InferenceMessage(BoundaryModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=100_000)


class InferenceRequest(BoundaryModel):
    messages: tuple[InferenceMessage, ...] = Field(min_length=1, max_length=100)
    record_references: tuple[RecordReference, ...] = Field(default=(), max_length=100)
    skill_ids: tuple[str, ...] = Field(default=(), max_length=20)
    tool_ids: tuple[str, ...] = Field(default=(), max_length=20)
    max_iterations: int = Field(default=4, ge=1, le=8)
    max_tool_calls: int = Field(default=8, ge=0, le=32)


class InferenceEvent(BoundaryModel):
    type: Literal["text_delta", "tool_request", "usage", "completed", "error"]
    text: str | None = Field(default=None, max_length=100_000)
    tool_id: str | None = Field(default=None, max_length=120)
    error_code: str | None = Field(default=None, max_length=80)
    usage: dict[str, int] | None = None


class StructuredProposal(BoundaryModel):
    """Validated proof payload for provider structured-output support."""

    summary: str = Field(min_length=1, max_length=12_000)
    source_references: tuple[str, ...] = Field(default=(), max_length=100)
    limitations: tuple[str, ...] = Field(default=(), max_length=100)
