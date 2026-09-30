from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Framework(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "frameworks"

    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")


class FrameworkVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "framework_versions"
    __table_args__ = (
        UniqueConstraint("framework_id", "version", name="uq_framework_version_framework_version"),
    )

    framework_id: Mapped[UUID] = mapped_column(
        ForeignKey("frameworks.id", ondelete="CASCADE"),
        index=True,
    )
    version: Mapped[str] = mapped_column(String(120))
    source_uri: Mapped[str] = mapped_column(String(1000))
    source_hash: Mapped[str] = mapped_column(String(64))
    verified_on: Mapped[date]
    published_at: Mapped[date | None]
    disclaimer: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FrameworkDomain(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "framework_domains"
    __table_args__ = (
        UniqueConstraint(
            "framework_version_id",
            "external_id",
            name="uq_framework_domain_version_external_id",
        ),
    )

    framework_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("framework_versions.id", ondelete="CASCADE"),
        index=True,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("framework_domains.id", ondelete="RESTRICT"),
    )
    external_id: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(default=0)


class FrameworkRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "framework_requirements"
    __table_args__ = (
        UniqueConstraint(
            "framework_version_id",
            "external_id",
            name="uq_framework_requirement_version_external_id",
        ),
        Index("ix_framework_requirement_domain_sort", "domain_id", "sort_order"),
    )

    framework_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("framework_versions.id", ondelete="CASCADE"),
        index=True,
    )
    domain_id: Mapped[UUID] = mapped_column(
        ForeignKey("framework_domains.id", ondelete="RESTRICT"),
        index=True,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("framework_requirements.id", ondelete="RESTRICT"),
    )
    external_id: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(400))
    summary: Mapped[str] = mapped_column(Text)
    guidance: Mapped[str] = mapped_column(Text, default="")
    source_reference: Mapped[str] = mapped_column(String(1000), default="")
    sort_order: Mapped[int] = mapped_column(default=0)
