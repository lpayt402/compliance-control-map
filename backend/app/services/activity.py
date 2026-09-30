from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActivityEvent, User

FIELD_LABELS = {
    "applicability": "Applicability",
    "assignee_user_id": "Assignee",
    "body": "Text",
    "contact_user_id": "Contact",
    "coverage": "Coverage",
    "description": "Description",
    "due_date": "Due date",
    "implementation_notes": "Implementation notes",
    "kind": "Resource type",
    "name": "Name",
    "owner_user_id": "Owner",
    "rationale": "Rationale",
    "status_code": "Readiness",
    "tags": "Tags",
    "title": "Title",
}


def record_activity(
    session: Session,
    *,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    entity_type: str,
    entity_id: UUID,
    action_code: str,
    before: dict[str, object] | None,
    after: dict[str, object] | None,
) -> ActivityEvent:
    event = ActivityEvent(
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action_code=action_code,
        before_snapshot=before,
        after_snapshot=after,
        created_at=datetime.now(UTC),
    )
    session.add(event)
    session.flush()
    return event


def activity_data(session: Session, event: ActivityEvent) -> dict[str, object]:
    actor_name = None
    if event.actor_user_id is not None:
        actor_name = session.scalar(
            select(User.display_name).where(
                User.id == event.actor_user_id,
                User.workspace_id == event.workspace_id,
            )
        )
    before = event.before_snapshot or {}
    after = event.after_snapshot or {}
    changed_keys = sorted(
        key for key in set(before) | set(after) if before.get(key) != after.get(key)
    )
    changed_labels = [
        FIELD_LABELS.get(key, key.replace("_", " ").capitalize()) for key in changed_keys
    ]
    return {
        "id": str(event.id),
        "action_code": event.action_code,
        "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
        "actor_display_name": actor_name,
        "change_summary": f"Changed: {', '.join(changed_labels)}" if changed_labels else None,
        "before": event.before_snapshot,
        "after": event.after_snapshot,
        "created_at": event.created_at.isoformat(),
    }


def list_requirement_activity(
    session: Session,
    workspace_id: UUID,
    requirement_id: UUID,
) -> list[ActivityEvent]:
    return list(
        session.scalars(
            select(ActivityEvent)
            .where(
                ActivityEvent.workspace_id == workspace_id,
                ActivityEvent.entity_type == "FRAMEWORK_REQUIREMENT",
                ActivityEvent.entity_id == requirement_id,
            )
            .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
        )
    )


def list_control_activity(
    session: Session,
    workspace_id: UUID,
    control_id: UUID,
) -> list[ActivityEvent]:
    return list(
        session.scalars(
            select(ActivityEvent)
            .where(
                ActivityEvent.workspace_id == workspace_id,
                ActivityEvent.entity_type == "ORGANIZATIONAL_CONTROL",
                ActivityEvent.entity_id == control_id,
            )
            .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
        )
    )
