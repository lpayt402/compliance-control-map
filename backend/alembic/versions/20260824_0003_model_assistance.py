"""bounded model-assistance profiles and run history

Revision ID: 20260824_0003
Revises: 20260824_0002
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_0003"
down_revision: str | None = "20260824_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inference_provider_profiles",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("provider_identifier", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("base_url", sa.String(length=1000), nullable=False),
        sa.Column("model_id", sa.String(length=200), nullable=False),
        sa.Column("api_mode", sa.String(length=32), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("tls_policy", sa.String(length=32), nullable=False),
        sa.Column("data_policy", sa.String(length=32), nullable=False),
        sa.Column("secret_ref", sa.String(length=240), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(length=32), nullable=True),
        sa.Column("last_test_latency_ms", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("api_mode IN ('CHAT_COMPLETIONS')", name="inference_provider_api_mode"),
        sa.CheckConstraint(
            "tls_policy IN ('REQUIRED', 'PRIVATE_CA_ALLOWED', 'PLAINTEXT_LOCAL_ONLY')",
            name="inference_provider_tls_policy",
        ),
        sa.CheckConstraint(
            "data_policy IN ('LOCAL_ONLY', 'REDACTED_EXTERNAL', 'EXTERNAL_ALLOWED')",
            name="inference_provider_data_policy",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_inference_provider_profiles_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inference_provider_profiles")),
        sa.UniqueConstraint(
            "workspace_id",
            "provider_identifier",
            name="uq_inference_provider_workspace_identifier",
        ),
    )
    with op.batch_alter_table("inference_provider_profiles") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_inference_provider_profiles_workspace_id"),
            ["workspace_id"],
            unique=False,
        )

    op.create_table(
        "inference_runs",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("provider_profile_id", sa.Uuid(), nullable=True),
        sa.Column("provider_identifier_snapshot", sa.String(length=80), nullable=False),
        sa.Column("provider_display_name_snapshot", sa.String(length=160), nullable=False),
        sa.Column("base_url_snapshot", sa.String(length=1000), nullable=False),
        sa.Column("model_id_snapshot", sa.String(length=200), nullable=False),
        sa.Column("agent_id", sa.String(length=120), nullable=False),
        sa.Column("skill_id", sa.String(length=120), nullable=False),
        sa.Column("skill_version", sa.String(length=40), nullable=False),
        sa.Column("record_references", sa.JSON(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("context_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("output_text", sa.Text(), nullable=False),
        sa.Column("structured_result", sa.JSON(), nullable=True),
        sa.Column("usage_metrics", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False),
        sa.Column("feedback_rating", sa.String(length=20), nullable=True),
        sa.Column("feedback_comment", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('STARTED', 'COMPLETED', 'FAILED', 'CANCELLED', 'TIMED_OUT')",
            name="inference_run_status",
        ),
        sa.CheckConstraint(
            "feedback_rating IS NULL OR feedback_rating IN ('USEFUL', 'NOT_USEFUL')",
            name="inference_run_feedback_rating",
        ),
        sa.ForeignKeyConstraint(
            ["provider_profile_id"],
            ["inference_provider_profiles.id"],
            name=op.f("fk_inference_runs_provider_profile_id_inference_provider_profiles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_inference_runs_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_inference_runs_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inference_runs")),
    )
    with op.batch_alter_table("inference_runs") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_inference_runs_provider_profile_id"),
            ["provider_profile_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_inference_runs_status"), ["status"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_inference_runs_workspace_id"), ["workspace_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("inference_runs") as batch_op:
        batch_op.drop_index(batch_op.f("ix_inference_runs_workspace_id"))
        batch_op.drop_index(batch_op.f("ix_inference_runs_status"))
        batch_op.drop_index(batch_op.f("ix_inference_runs_provider_profile_id"))
    op.drop_table("inference_runs")
    with op.batch_alter_table("inference_provider_profiles") as batch_op:
        batch_op.drop_index(batch_op.f("ix_inference_provider_profiles_workspace_id"))
    op.drop_table("inference_provider_profiles")
