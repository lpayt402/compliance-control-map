from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OrganizationalControl(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "organizational_controls"
    __table_args__ = (
        UniqueConstraint("workspace_id", "code", name="uq_control_workspace_code"),
        ForeignKeyConstraint(
            ["workspace_id", "status_code"],
            ["status_definitions.workspace_id", "status_definitions.code"],
            name="fk_control_workspace_status",
            ondelete="RESTRICT",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    status_code: Mapped[str] = mapped_column(String(40), default="PLANNED")
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    implementation_notes: Mapped[str] = mapped_column(Text, default="")


class ControlNote(UUIDPrimaryKeyMixin, RevisionMixin, Base):
    __tablename__ = "control_notes"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('NOTE', 'PLAYBOOK', 'CONTACT')",
            name="control_note_kind",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    control_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizational_controls.id", ondelete="CASCADE"),
        index=True,
    )
    author_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    contact_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    kind: Mapped[str] = mapped_column(String(16), default="NOTE")
    title: Mapped[str] = mapped_column(String(240), default="")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RequirementControlMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "requirement_control_mappings"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "requirement_id",
            "control_id",
            name="uq_requirement_control_mapping_pair",
        ),
        CheckConstraint(
            "coverage IN ('PRIMARY', 'SUPPORTING', 'LIMITED')",
            name="requirement_control_mapping_coverage",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("framework_requirements.id", ondelete="CASCADE"),
        index=True,
    )
    control_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizational_controls.id", ondelete="CASCADE"),
        index=True,
    )
    coverage: Mapped[str] = mapped_column(String(24), default="SUPPORTING")
    rationale: Mapped[str] = mapped_column(Text, default="")


class RequirementMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "requirement_mappings"
    __table_args__ = (
        CheckConstraint(
            "source_requirement_id <> target_requirement_id",
            name="ck_requirement_mapping_distinct",
        ),
        CheckConstraint(
            "relationship_type IN ('EQUIVALENT', 'STRONG_OVERLAP', 'PARTIAL_OVERLAP', 'RELATED')",
            name="ck_requirement_mapping_relationship_type",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 100)",
            name="ck_requirement_mapping_confidence",
        ),
        UniqueConstraint(
            "source_requirement_id",
            "target_requirement_id",
            "relationship_type",
            name="uq_requirement_mapping_direction_type",
        ),
    )

    workspace_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    source_requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("framework_requirements.id", ondelete="CASCADE"),
        index=True,
    )
    target_requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("framework_requirements.id", ondelete="CASCADE"),
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[int | None] = mapped_column(Integer)
    mapping_source: Mapped[str] = mapped_column(String(400))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )


class ControlTag(Base):
    __tablename__ = "control_tags"
    __table_args__ = (UniqueConstraint("control_id", "tag_id", name="uq_control_tag_pair"),)

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    control_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizational_controls.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[UUID] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
