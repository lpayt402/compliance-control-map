import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import Principal, Role
from app.models import InferenceProviderProfile, InferenceRun
from app.services.activity import record_activity


class RunNotFound(LookupError):
    pass


class RunLimiter:
    def __init__(self, max_workspace_runs: int) -> None:
        self._max_workspace_runs = max_workspace_runs
        self._workspace_counts: dict[UUID, int] = defaultdict(int)
        self._user_keys: set[tuple[UUID, UUID | None]] = set()
        self._lock = asyncio.Lock()

    async def acquire(self, workspace_id: UUID, user_id: UUID | None) -> bool:
        async with self._lock:
            user_key = (workspace_id, user_id)
            if (
                self._workspace_counts[workspace_id] >= self._max_workspace_runs
                or user_key in self._user_keys
            ):
                return False
            self._workspace_counts[workspace_id] += 1
            self._user_keys.add(user_key)
            return True

    async def release(self, workspace_id: UUID, user_id: UUID | None) -> None:
        async with self._lock:
            user_key = (workspace_id, user_id)
            self._user_keys.discard(user_key)
            remaining = self._workspace_counts.get(workspace_id, 0) - 1
            if remaining > 0:
                self._workspace_counts[workspace_id] = remaining
            else:
                self._workspace_counts.pop(workspace_id, None)


def create_run(
    db: Session,
    principal: Principal,
    provider: InferenceProviderProfile,
    *,
    agent_id: str,
    skill_id: str,
    skill_version: str,
    record_references: list[dict[str, object]],
    instruction: str,
    context_digest: str,
) -> InferenceRun:
    now = datetime.now(UTC)
    run = InferenceRun(
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        provider_profile_id=provider.id,
        provider_identifier_snapshot=provider.provider_identifier,
        provider_display_name_snapshot=provider.display_name,
        base_url_snapshot=provider.base_url,
        model_id_snapshot=provider.model_id,
        agent_id=agent_id,
        skill_id=skill_id,
        skill_version=skill_version,
        record_references=record_references,
        instruction=instruction,
        context_digest=context_digest,
        status="STARTED",
        started_at=now,
        output_text="",
        cancellation_requested=False,
        created_at=now,
    )
    db.add(run)
    db.flush()
    record_activity(
        db,
        workspace_id=principal.workspace_id,
        actor_user_id=principal.user_id,
        entity_type="INFERENCE_RUN",
        entity_id=run.id,
        action_code="MODEL_RUN_STARTED",
        before=None,
        after={
            "provider_identifier": provider.provider_identifier,
            "model_id": provider.model_id,
            "agent_id": agent_id,
            "skill_id": skill_id,
            "status": "STARTED",
        },
    )
    return run


def finish_run(
    db: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    run_id: UUID,
    *,
    status: str,
    output_text: str,
    structured_result: dict[str, object] | None = None,
    usage_metrics: dict[str, object] | None = None,
    error_code: str | None = None,
    error_summary: str | None = None,
) -> InferenceRun:
    run = db.scalar(
        select(InferenceRun).where(
            InferenceRun.id == run_id,
            InferenceRun.workspace_id == workspace_id,
        )
    )
    if run is None:
        raise RunNotFound
    finished_at = datetime.now(UTC)
    started_at = run.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    run.status = status
    run.finished_at = finished_at
    run.duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1_000))
    run.output_text = output_text
    run.structured_result = structured_result
    run.usage_metrics = usage_metrics
    run.error_code = error_code
    run.error_summary = error_summary
    run.cancellation_requested = status == "CANCELLED"
    action = {
        "COMPLETED": "MODEL_RUN_COMPLETED",
        "FAILED": "MODEL_RUN_FAILED",
        "CANCELLED": "MODEL_RUN_CANCELLED",
        "TIMED_OUT": "MODEL_RUN_FAILED",
    }[status]
    record_activity(
        db,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="INFERENCE_RUN",
        entity_id=run.id,
        action_code=action,
        before={"status": "STARTED"},
        after={
            "status": status,
            "error_code": error_code,
            "duration_ms": run.duration_ms,
        },
    )
    return run


def _utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.isoformat().replace("+00:00", "Z")


def run_response(run: InferenceRun) -> dict[str, object]:
    return {
        "id": str(run.id),
        "provider_profile_id": str(run.provider_profile_id) if run.provider_profile_id else None,
        "provider_identifier": run.provider_identifier_snapshot,
        "provider_display_name": run.provider_display_name_snapshot,
        "base_url": run.base_url_snapshot,
        "model_id": run.model_id_snapshot,
        "agent_id": run.agent_id,
        "skill_id": run.skill_id,
        "skill_version": run.skill_version,
        "record_references": run.record_references,
        "instruction": run.instruction,
        "context_digest": run.context_digest,
        "status": run.status,
        "started_at": _utc(run.started_at),
        "finished_at": _utc(run.finished_at),
        "duration_ms": run.duration_ms,
        "output_text": run.output_text,
        "structured_result": run.structured_result,
        "usage_metrics": run.usage_metrics,
        "error_code": run.error_code,
        "error_summary": run.error_summary,
        "cancellation_requested": run.cancellation_requested,
        "feedback_rating": run.feedback_rating,
        "feedback_comment": run.feedback_comment,
    }


def list_runs(db: Session, principal: Principal) -> list[InferenceRun]:
    query = select(InferenceRun).where(InferenceRun.workspace_id == principal.workspace_id)
    if principal.role is not Role.ADMIN:
        query = query.where(InferenceRun.user_id == principal.user_id)
    return list(
        db.scalars(query.order_by(InferenceRun.created_at.desc(), InferenceRun.id.desc()))
    )


def get_run(db: Session, principal: Principal, run_id: UUID) -> InferenceRun:
    query = select(InferenceRun).where(
        InferenceRun.id == run_id,
        InferenceRun.workspace_id == principal.workspace_id,
    )
    if principal.role is not Role.ADMIN:
        query = query.where(InferenceRun.user_id == principal.user_id)
    run = db.scalar(query)
    if run is None:
        raise RunNotFound
    return run


def record_feedback(
    db: Session,
    principal: Principal,
    run_id: UUID,
    *,
    rating: str,
    comment: str | None,
) -> InferenceRun:
    run = get_run(db, principal, run_id)
    run.feedback_rating = rating
    run.feedback_comment = comment.strip() if comment and comment.strip() else None
    record_activity(
        db,
        workspace_id=principal.workspace_id,
        actor_user_id=principal.user_id,
        entity_type="INFERENCE_RUN",
        entity_id=run.id,
        action_code="MODEL_RUN_FEEDBACK_RECORDED",
        before=None,
        after={"rating": rating, "has_comment": bool(run.feedback_comment)},
    )
    return run
