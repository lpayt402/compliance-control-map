import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session as OrmSession

from app.models import Session, User

SESSION_LIFETIME = timedelta(hours=12)


@dataclass(frozen=True)
class CreatedSession:
    token: str
    csrf_token: str
    record: Session


def session_cookie_name(production: bool) -> str:
    return "__Host-ccm_session" if production else "ccm_session"


def csrf_cookie_name(production: bool) -> str:
    return "__Host-ccm_csrf" if production else "ccm_csrf"


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: OrmSession, user: User, now: datetime | None = None) -> CreatedSession:
    created_at = now or datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    record = Session(
        workspace_id=user.workspace_id,
        user_id=user.id,
        secret_hash=hash_session_token(token),
        csrf_secret=csrf_token,
        created_at=created_at,
        expires_at=created_at + SESSION_LIFETIME,
        last_seen_at=created_at,
    )
    db.add(record)
    db.flush()
    return CreatedSession(token=token, csrf_token=csrf_token, record=record)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def active_session(
    db: OrmSession,
    token: str | None,
    now: datetime | None = None,
) -> tuple[Session, User] | None:
    if not token:
        return None
    current_time = now or datetime.now(UTC)
    record = db.scalar(
        select(Session).where(Session.secret_hash == hash_session_token(token))
    )
    if (
        record is None
        or record.revoked_at is not None
        or _as_utc(record.expires_at) <= current_time
    ):
        return None
    user = db.get(User, record.user_id)
    if user is None or user.is_disabled or not user.can_login:
        return None
    record.last_seen_at = current_time
    return record, user


def revoke_session(record: Session, now: datetime | None = None) -> None:
    record.revoked_at = now or datetime.now(UTC)


def revoke_user_sessions(
    db: OrmSession,
    user_id: UUID,
    now: datetime | None = None,
) -> None:
    db.execute(
        update(Session)
        .where(Session.user_id == user_id, Session.revoked_at.is_(None))
        .values(revoked_at=now or datetime.now(UTC))
    )
