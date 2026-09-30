from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, RevisionMixin, TimestampMixin, UUIDPrimaryKeyMixin


class StoredFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stored_files"
    __table_args__ = (
        UniqueConstraint("workspace_id", "storage_key", name="uq_stored_file_workspace_key"),
        UniqueConstraint("workspace_id", "sha256", name="uq_stored_file_workspace_sha256"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    storage_key: Mapped[str] = mapped_column(String(240))
    original_filename: Mapped[str] = mapped_column(String(500))
    normalized_extension: Mapped[str] = mapped_column(String(20))
    declared_media_type: Mapped[str] = mapped_column(String(200))
    detected_media_type: Mapped[str] = mapped_column(String(200))
    byte_size: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )


class Document(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ('POLICY', 'STANDARD', 'PROCEDURE', 'PLAN', 'GUIDELINE', 'OTHER')",
            name="ck_document_type",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    stored_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("stored_files.id", ondelete="RESTRICT"),
    )
    name: Mapped[str] = mapped_column(String(300))
    document_type: Mapped[str] = mapped_column(String(24), default="OTHER")
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[str] = mapped_column(String(80), default="")
    effective_date: Mapped[date | None]
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    notes: Mapped[str] = mapped_column(Text, default="")


class Evidence(UUIDPrimaryKeyMixin, RevisionMixin, TimestampMixin, Base):
    __tablename__ = "evidence"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    stored_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("stored_files.id", ondelete="RESTRICT"),
    )
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    evidence_date: Mapped[date | None]
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    notes: Mapped[str] = mapped_column(Text, default="")


class ControlDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_documents"
    __table_args__ = (
        UniqueConstraint("control_id", "document_id", name="uq_control_document_pair"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    control_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizational_controls.id", ondelete="CASCADE"),
    )
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))


class ControlEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_evidence"
    __table_args__ = (
        UniqueConstraint("control_id", "evidence_id", name="uq_control_evidence_pair"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    control_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizational_controls.id", ondelete="CASCADE"),
    )
    evidence_id: Mapped[UUID] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"))


class RequirementDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "requirement_documents"
    __table_args__ = (
        UniqueConstraint("requirement_id", "document_id", name="uq_requirement_document_pair"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("framework_requirements.id", ondelete="CASCADE"),
    )
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    rationale: Mapped[str] = mapped_column(Text, default="")


class RequirementEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "requirement_evidence"
    __table_args__ = (
        UniqueConstraint("requirement_id", "evidence_id", name="uq_requirement_evidence_pair"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("framework_requirements.id", ondelete="CASCADE"),
    )
    evidence_id: Mapped[UUID] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"))
    rationale: Mapped[str] = mapped_column(Text, default="")
