from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(240))
    timezone: Mapped[str] = mapped_column(String(80), default="UTC")
    locale: Mapped[str] = mapped_column(String(40), default="en-US")


class StatusDefinition(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "status_definitions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "code", name="uq_status_definition_workspace_code"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    scope: Mapped[str] = mapped_column(String(24))
    code: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    color_token: Mapped[str] = mapped_column(String(40))
    icon: Mapped[str] = mapped_column(String(40))
    sort_order: Mapped[int]
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False)


class Tag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_tag_workspace_name"),)

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80))
