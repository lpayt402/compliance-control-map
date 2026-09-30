from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin


class RequirementAssessment(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "requirement_assessments"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "requirement_id",
            name="uq_requirement_assessment_workspace_requirement",
        ),
        CheckConstraint(
            "applicability IN ('UNDETERMINED', 'APPLICABLE', 'NOT_APPLICABLE')",
            name="requirement_assessment_applicability",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "status_code"],
            ["status_definitions.workspace_id", "status_definitions.code"],
            name="fk_requirement_assessment_workspace_status",
            ondelete="RESTRICT",
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
    status_code: Mapped[str] = mapped_column(String(40), default="NOT_ASSESSED")
    applicability: Mapped[str] = mapped_column(String(24), default="UNDETERMINED")
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    assignee_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    due_date: Mapped[date | None]
    implementation_notes: Mapped[str] = mapped_column(Text, default="")


class AssessmentTag(Base):
    __tablename__ = "assessment_tags"
    __table_args__ = (UniqueConstraint("assessment_id", "tag_id", name="uq_assessment_tag_pair"),)

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("requirement_assessments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[UUID] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )


class RequirementNote(UUIDPrimaryKeyMixin, RevisionMixin, Base):
    __tablename__ = "requirement_notes"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("requirement_assessments.id", ondelete="CASCADE"),
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
