import os
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.inference.models import DataPolicy, ProviderCapabilities, TLSPolicy
from app.inference.policy import DestinationPolicyError, validate_provider_destination
from app.models import InferenceProviderProfile
from app.schemas.inference import ProviderProfileCreate, ProviderProfileResponse
from app.services.activity import record_activity


class ProviderNotFound(LookupError):
    pass


class ProviderConflict(RuntimeError):
    pass


class ProviderValidationError(ValueError):
    pass


def _secret_value(secret_ref: str | None) -> str | None:
    if secret_ref is None:
        return None
    prefix, variable = secret_ref.split(":", 1)
    if prefix != "env":
        return None
    value = os.getenv(variable)
    return value if value else None


def secret_status(secret_ref: str | None) -> str:
    if secret_ref is None:
        return "NOT_REQUIRED"
    return "CONFIGURED" if _secret_value(secret_ref) is not None else "MISSING"


def resolve_provider_secret(profile: InferenceProviderProfile) -> str | None:
    return _secret_value(profile.secret_ref)


def provider_response(profile: InferenceProviderProfile) -> dict[str, object]:
    def utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    return ProviderProfileResponse(
        id=profile.id,
        provider_identifier=profile.provider_identifier,
        display_name=profile.display_name,
        base_url=profile.base_url,
        model_id=profile.model_id,
        api_mode="CHAT_COMPLETIONS",
        capabilities=ProviderCapabilities.model_validate(profile.capabilities),
        timeout_seconds=profile.timeout_seconds,
        tls_policy=TLSPolicy(profile.tls_policy),
        data_policy=DataPolicy(profile.data_policy),
        secret_status=secret_status(profile.secret_ref),
        enabled=profile.enabled,
        is_default=profile.is_default,
        last_tested_at=utc(profile.last_tested_at),
        last_test_status=profile.last_test_status,
        last_test_latency_ms=profile.last_test_latency_ms,
        revision=profile.revision,
        created_at=utc(profile.created_at),
        updated_at=utc(profile.updated_at),
    ).model_dump(mode="json")


def _safe_snapshot(profile: InferenceProviderProfile) -> dict[str, object]:
    return {
        "provider_identifier": profile.provider_identifier,
        "model_id": profile.model_id,
        "enabled": profile.enabled,
        "is_default": profile.is_default,
        "tls_policy": profile.tls_policy,
        "data_policy": profile.data_policy,
    }


def _validate(
    settings: Settings,
    *,
    base_url: str,
    tls_policy: str,
    data_policy: str,
    secret_ref: str | None,
    enabled: bool,
    is_default: bool,
) -> str:
    try:
        normalized = validate_provider_destination(
            base_url,
            allowed_base_urls=settings.inference_allowed_base_urls,
            tls_policy=TLSPolicy(tls_policy),
            data_policy=DataPolicy(data_policy),
        )
    except (DestinationPolicyError, ValueError) as exc:
        raise ProviderValidationError(str(exc)) from exc
    if enabled and not settings.inference_enabled:
        raise ProviderValidationError("Model assistance is disabled by the server kill switch.")
    if enabled and secret_ref is not None and _secret_value(secret_ref) is None:
        raise ProviderValidationError("The provider secret reference is missing.")
    if is_default and not enabled:
        raise ProviderValidationError("The default provider must be enabled.")
    return normalized


def list_providers(db: Session, workspace_id: UUID) -> list[InferenceProviderProfile]:
    return list(
        db.scalars(
            select(InferenceProviderProfile)
            .where(InferenceProviderProfile.workspace_id == workspace_id)
            .order_by(InferenceProviderProfile.display_name, InferenceProviderProfile.id)
        )
    )


def get_provider(db: Session, workspace_id: UUID, profile_id: UUID) -> InferenceProviderProfile:
    profile = db.scalar(
        select(InferenceProviderProfile).where(
            InferenceProviderProfile.id == profile_id,
            InferenceProviderProfile.workspace_id == workspace_id,
        )
    )
    if profile is None:
        raise ProviderNotFound
    return profile


def _clear_default(db: Session, workspace_id: UUID, *, except_id: UUID) -> None:
    db.execute(
        update(InferenceProviderProfile)
        .where(
            InferenceProviderProfile.workspace_id == workspace_id,
            InferenceProviderProfile.id != except_id,
            InferenceProviderProfile.is_default.is_(True),
        )
        .values(is_default=False, revision=InferenceProviderProfile.revision + 1)
    )


def create_provider(
    db: Session,
    settings: Settings,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    payload: ProviderProfileCreate,
) -> InferenceProviderProfile:
    normalized = _validate(
        settings,
        base_url=payload.base_url,
        tls_policy=payload.tls_policy.value,
        data_policy=payload.data_policy.value,
        secret_ref=payload.secret_ref,
        enabled=payload.enabled,
        is_default=payload.is_default,
    )
    profile = InferenceProviderProfile(
        workspace_id=workspace_id,
        provider_identifier=payload.provider_identifier,
        display_name=payload.display_name,
        base_url=normalized,
        model_id=payload.model_id,
        api_mode=payload.api_mode,
        capabilities=payload.capabilities.model_dump(mode="json"),
        timeout_seconds=payload.timeout_seconds,
        tls_policy=payload.tls_policy.value,
        data_policy=payload.data_policy.value,
        secret_ref=payload.secret_ref,
        enabled=payload.enabled,
        is_default=payload.is_default,
    )
    db.add(profile)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ProviderConflict("Provider identifier already exists in this workspace.") from exc
    if profile.is_default:
        _clear_default(db, workspace_id, except_id=profile.id)
    record_activity(
        db,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="INFERENCE_PROVIDER",
        entity_id=profile.id,
        action_code="PROVIDER_CREATED",
        before=None,
        after=_safe_snapshot(profile),
    )
    return profile


def update_provider(
    db: Session,
    settings: Settings,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    profile_id: UUID,
    *,
    expected_revision: int,
    changes: dict[str, object],
) -> InferenceProviderProfile:
    profile = get_provider(db, workspace_id, profile_id)
    if profile.revision != expected_revision:
        raise ProviderConflict("Provider profile was changed by another request.")
    before = _safe_snapshot(profile)
    candidate = {
        "base_url": changes.get("base_url", profile.base_url),
        "tls_policy": changes.get("tls_policy", profile.tls_policy),
        "data_policy": changes.get("data_policy", profile.data_policy),
        "secret_ref": changes.get("secret_ref", profile.secret_ref),
        "enabled": changes.get("enabled", profile.enabled),
        "is_default": changes.get("is_default", profile.is_default),
    }
    normalized = _validate(
        settings,
        base_url=str(candidate["base_url"]),
        tls_policy=str(candidate["tls_policy"]),
        data_policy=str(candidate["data_policy"]),
        secret_ref=candidate["secret_ref"] if isinstance(candidate["secret_ref"], str) else None,
        enabled=bool(candidate["enabled"]),
        is_default=bool(candidate["is_default"]),
    )
    changes["base_url"] = normalized
    for field, value in changes.items():
        if field == "capabilities" and isinstance(value, ProviderCapabilities):
            value = value.model_dump(mode="json")
        if isinstance(value, (TLSPolicy, DataPolicy)):
            value = value.value
        setattr(profile, field, value)
    profile.revision += 1
    db.flush()
    if profile.is_default:
        _clear_default(db, workspace_id, except_id=profile.id)
    record_activity(
        db,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="INFERENCE_PROVIDER",
        entity_id=profile.id,
        action_code="PROVIDER_UPDATED",
        before=before,
        after=_safe_snapshot(profile),
    )
    return profile


def delete_provider(
    db: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    profile_id: UUID,
) -> None:
    profile = get_provider(db, workspace_id, profile_id)
    before = _safe_snapshot(profile)
    db.delete(profile)
    record_activity(
        db,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="INFERENCE_PROVIDER",
        entity_id=profile.id,
        action_code="PROVIDER_DELETED",
        before=before,
        after=None,
    )


def record_provider_test(
    db: Session,
    workspace_id: UUID,
    actor_user_id: UUID | None,
    profile_id: UUID,
    *,
    reachable: bool,
    latency_ms: int,
) -> None:
    profile = get_provider(db, workspace_id, profile_id)
    profile.last_tested_at = datetime.now(UTC)
    profile.last_test_status = "REACHABLE" if reachable else "UNREACHABLE"
    profile.last_test_latency_ms = latency_ms
    profile.revision += 1
    record_activity(
        db,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        entity_type="INFERENCE_PROVIDER",
        entity_id=profile.id,
        action_code="PROVIDER_TESTED",
        before=None,
        after={
            "outcome": profile.last_test_status,
            "latency_ms": latency_ms,
        },
    )
