from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin


class InferenceProviderProfile(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "inference_provider_profiles"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "provider_identifier",
            name="uq_inference_provider_workspace_identifier",
        ),
        CheckConstraint("api_mode IN ('CHAT_COMPLETIONS')", name="inference_provider_api_mode"),
        CheckConstraint(
            "tls_policy IN ('REQUIRED', 'PRIVATE_CA_ALLOWED', 'PLAINTEXT_LOCAL_ONLY')",
            name="inference_provider_tls_policy",
        ),
        CheckConstraint(
            "data_policy IN ('LOCAL_ONLY', 'REDACTED_EXTERNAL', 'EXTERNAL_ALLOWED')",
            name="inference_provider_data_policy",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    provider_identifier: Mapped[str] = mapped_column(String(80))
    display_name: Mapped[str] = mapped_column(String(160))
    base_url: Mapped[str] = mapped_column(String(1_000))
    model_id: Mapped[str] = mapped_column(String(200))
    api_mode: Mapped[str] = mapped_column(String(32), default="CHAT_COMPLETIONS")
    capabilities: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60)
    tls_policy: Mapped[str] = mapped_column(String(32))
    data_policy: Mapped[str] = mapped_column(String(32))
    secret_ref: Mapped[str | None] = mapped_column(String(240))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_status: Mapped[str | None] = mapped_column(String(32))
    last_test_latency_ms: Mapped[int | None] = mapped_column(Integer)


class InferenceRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "inference_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('STARTED', 'COMPLETED', 'FAILED', 'CANCELLED', 'TIMED_OUT')",
            name="inference_run_status",
        ),
        CheckConstraint(
            "feedback_rating IS NULL OR feedback_rating IN ('USEFUL', 'NOT_USEFUL')",
            name="inference_run_feedback_rating",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    provider_profile_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("inference_provider_profiles.id", ondelete="SET NULL"),
        index=True,
    )
    provider_identifier_snapshot: Mapped[str] = mapped_column(String(80))
    provider_display_name_snapshot: Mapped[str] = mapped_column(String(160))
    base_url_snapshot: Mapped[str] = mapped_column(String(1_000))
    model_id_snapshot: Mapped[str] = mapped_column(String(200))
    agent_id: Mapped[str] = mapped_column(String(120))
    skill_id: Mapped[str] = mapped_column(String(120))
    skill_version: Mapped[str] = mapped_column(String(40))
    record_references: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    instruction: Mapped[str] = mapped_column(Text, default="")
    context_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    output_text: Mapped[str] = mapped_column(Text, default="")
    structured_result: Mapped[dict[str, object] | None] = mapped_column(JSON)
    usage_metrics: Mapped[dict[str, object] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_summary: Mapped[str | None] = mapped_column(String(500))
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback_rating: Mapped[str | None] = mapped_column(String(20))
    feedback_comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
