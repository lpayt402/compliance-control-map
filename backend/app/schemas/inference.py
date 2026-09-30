from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.inference.models import DataPolicy, ProviderCapabilities, RecordReference, TLSPolicy
from app.schemas.base import APIModel


class ProviderProfileCreate(APIModel):
    provider_identifier: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )
    display_name: str = Field(min_length=1, max_length=160)
    base_url: str = Field(min_length=1, max_length=1_000)
    model_id: str = Field(min_length=1, max_length=200)
    api_mode: Literal["CHAT_COMPLETIONS"] = "CHAT_COMPLETIONS"
    capabilities: ProviderCapabilities = ProviderCapabilities()
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    tls_policy: TLSPolicy = TLSPolicy.REQUIRED
    data_policy: DataPolicy = DataPolicy.LOCAL_ONLY
    secret_ref: str | None = Field(default=None, pattern=r"^env:[A-Z][A-Z0-9_]*$", max_length=240)
    enabled: bool = False
    is_default: bool = False


class ProviderProfileUpdate(APIModel):
    revision: int = Field(ge=1)
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    base_url: str | None = Field(default=None, min_length=1, max_length=1_000)
    model_id: str | None = Field(default=None, min_length=1, max_length=200)
    capabilities: ProviderCapabilities | None = None
    timeout_seconds: int | None = Field(default=None, ge=5, le=300)
    tls_policy: TLSPolicy | None = None
    data_policy: DataPolicy | None = None
    secret_ref: str | None = Field(default=None, pattern=r"^env:[A-Z][A-Z0-9_]*$", max_length=240)
    enabled: bool | None = None
    is_default: bool | None = None


class ProviderProfileResponse(APIModel):
    id: UUID
    provider_identifier: str
    display_name: str
    base_url: str
    model_id: str
    api_mode: Literal["CHAT_COMPLETIONS"]
    capabilities: ProviderCapabilities
    timeout_seconds: int
    tls_policy: TLSPolicy
    data_policy: DataPolicy
    secret_status: Literal["CONFIGURED", "MISSING", "NOT_REQUIRED"]
    enabled: bool
    is_default: bool
    last_tested_at: datetime | None
    last_test_status: str | None
    last_test_latency_ms: int | None
    revision: int
    created_at: datetime
    updated_at: datetime


class ContextPreviewRequest(APIModel):
    skill_id: str = Field(min_length=1, max_length=120)
    record_references: tuple[RecordReference, ...] = Field(min_length=1, max_length=20)
    instruction: str = Field(default="", max_length=4_000)
    include_text_resources: bool = True
    include_mapped_resources: bool = True


class RunStartRequest(ContextPreviewRequest):
    provider_profile_id: UUID
    agent_id: str = Field(default="compliance-assistant", max_length=120)
    context_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    external_transfer_confirmed: bool = False


class RunFeedbackRequest(APIModel):
    rating: Literal["USEFUL", "NOT_USEFUL"]
    comment: str | None = Field(default=None, max_length=500)
