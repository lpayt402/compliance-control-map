from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class ActivityEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "activity_events"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[UUID]
    action_code: Mapped[str] = mapped_column(String(120), index=True)
    before_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON)
    after_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )
