from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.core.passwords import PasswordPolicyError, hash_password
from app.core.permissions import Principal, Role
from app.core.sessions import revoke_user_sessions
from app.models import ActivityEvent, User
from app.schemas.auth import UserCreate, UserResponse, UserUpdate
from app.services.activity import record_activity
from app.services.auth import CurrentPrincipal, require_role

router = APIRouter(prefix="/users", tags=["users"])
AdminPrincipal = Annotated[Principal, Depends(require_role(Role.ADMIN))]


def _serialize(user: User) -> dict[str, object]:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=Role(user.role),
        is_disabled=user.is_disabled,
    ).model_dump(mode="json")


def _snapshot(user: User) -> dict[str, object]:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_disabled": user.is_disabled,
    }


def _active_admin_count(db: OrmSession, workspace_id: UUID) -> int:
    count = db.scalar(
        select(func.count(User.id)).where(
            User.workspace_id == workspace_id,
            User.role == Role.ADMIN.value,
            User.is_disabled.is_(False),
        )
    )
    return int(count or 0)


def _guard_admin_access_change(
    db: OrmSession,
    user: User,
    principal: Principal,
    *,
    next_role: str,
    next_disabled: bool,
) -> None:
    removes_active_admin = (
        user.role == Role.ADMIN.value
        and not user.is_disabled
        and (next_role != Role.ADMIN.value or next_disabled)
    )
    if not removes_active_admin:
        return
    if user.id == principal.user_id:
        raise HTTPException(
            status_code=409,
            detail="You cannot remove your own administrator access.",
        )
    if _active_admin_count(db, principal.workspace_id) <= 1:
        raise HTTPException(
            status_code=409,
            detail="The workspace must keep at least one active administrator.",
        )


@router.get("")
def list_users(request: Request, principal: AdminPrincipal) -> dict[str, object]:
    database = request.app.state.database
    with database.session() as db:
        users = db.scalars(
            select(User)
            .where(User.workspace_id == principal.workspace_id)
            .order_by(User.display_name)
        ).all()
        data = [_serialize(user) for user in users]
    return {"data": data, "meta": {}}


@router.get("/directory")
def user_directory(request: Request, principal: CurrentPrincipal) -> dict[str, object]:
    """Return only the fields needed by owner and assignee selectors."""
    with request.app.state.database.session() as db:
        users = db.scalars(
            select(User)
            .where(
                User.workspace_id == principal.workspace_id,
                User.is_disabled.is_(False),
            )
            .order_by(User.display_name)
        ).all()
        data = [{"id": str(user.id), "display_name": user.display_name} for user in users]
    return {"data": data, "meta": {}}


@router.get("/activity")
def user_activity(request: Request, principal: AdminPrincipal) -> dict[str, object]:
    with request.app.state.database.session() as db:
        events = db.scalars(
            select(ActivityEvent)
            .where(
                ActivityEvent.workspace_id == principal.workspace_id,
                ActivityEvent.entity_type == "USER",
            )
            .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
            .limit(30)
        ).all()
        actor_ids = {event.actor_user_id for event in events if event.actor_user_id is not None}
        actors = {
            user.id: user.display_name
            for user in db.scalars(select(User).where(User.id.in_(actor_ids))).all()
        } if actor_ids else {}
        data = [
            {
                "id": str(event.id),
                "action_code": event.action_code,
                "entity_id": str(event.entity_id),
                "actor_display_name": actors.get(event.actor_user_id, "System"),
                "before": event.before_snapshot,
                "after": event.after_snapshot,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ]
    return {"data": data, "meta": {"count": len(data)}}


@router.post("", status_code=201)
def create_user(
    request: Request,
    payload: UserCreate,
    principal: AdminPrincipal,
) -> dict[str, object]:
    database = request.app.state.database
    normalized_email = str(payload.email).strip().casefold()
    try:
        password_hash = hash_password(payload.password)
    except PasswordPolicyError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    with database.session() as db:
        existing = db.scalar(
            select(User).where(
                User.workspace_id == principal.workspace_id,
                User.normalized_email == normalized_email,
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="A user with that email already exists.")
        user = User(
            workspace_id=principal.workspace_id,
            email=str(payload.email),
            normalized_email=normalized_email,
            display_name=payload.display_name,
            password_hash=password_hash,
            role=payload.role,
            can_login=True,
        )
        db.add(user)
        db.flush()
        record_activity(
            db,
            workspace_id=principal.workspace_id,
            actor_user_id=principal.user_id,
            entity_type="USER",
            entity_id=user.id,
            action_code="USER_CREATED",
            before=None,
            after=_snapshot(user),
        )
        data = _serialize(user)
    return {"data": data, "meta": {}}


@router.patch("/{user_id}")
def update_user(
    request: Request,
    user_id: UUID,
    payload: UserUpdate,
    principal: AdminPrincipal,
) -> dict[str, object]:
    database = request.app.state.database
    with database.session() as db:
        user = db.scalar(
            select(User).where(
                User.id == user_id,
                User.workspace_id == principal.workspace_id,
            )
        )
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")
        if payload.password is not None and user.id == principal.user_id:
            raise HTTPException(
                status_code=409,
                detail="Use Change my password for your own account.",
            )
        next_role = payload.role.value if payload.role is not None else user.role
        next_disabled = (
            payload.is_disabled if payload.is_disabled is not None else user.is_disabled
        )
        _guard_admin_access_change(
            db,
            user,
            principal,
            next_role=next_role,
            next_disabled=next_disabled,
        )
        password_hash: str | None = None
        if payload.password is not None:
            try:
                password_hash = hash_password(payload.password)
            except PasswordPolicyError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error

        before = _snapshot(user)
        changed_profile = False
        changed_access = password_hash is not None
        if payload.display_name is not None and payload.display_name != user.display_name:
            user.display_name = payload.display_name
            changed_profile = True
        if payload.role is not None and payload.role.value != user.role:
            user.role = payload.role.value
            changed_access = True
            changed_profile = True
        if payload.is_disabled is not None and payload.is_disabled != user.is_disabled:
            user.is_disabled = payload.is_disabled
            changed_access = True
            changed_profile = True
        after = _snapshot(user)
        if changed_profile:
            if before["is_disabled"] is False and user.is_disabled:
                action_code = "USER_DEACTIVATED"
            elif before["is_disabled"] is True and not user.is_disabled:
                action_code = "USER_REACTIVATED"
            else:
                action_code = "USER_UPDATED"
            record_activity(
                db,
                workspace_id=principal.workspace_id,
                actor_user_id=principal.user_id,
                entity_type="USER",
                entity_id=user.id,
                action_code=action_code,
                before=before,
                after=after,
            )
        if password_hash is not None:
            user.password_hash = password_hash
            record_activity(
                db,
                workspace_id=principal.workspace_id,
                actor_user_id=principal.user_id,
                entity_type="USER",
                entity_id=user.id,
                action_code="USER_PASSWORD_RESET",
                before=before,
                after=after,
            )
        if changed_access:
            revoke_user_sessions(db, user.id)
        data = _serialize(user)
    return {"data": data, "meta": {}}


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    request: Request,
    user_id: UUID,
    principal: AdminPrincipal,
) -> None:
    with request.app.state.database.session() as db:
        user = db.scalar(
            select(User).where(
                User.id == user_id,
                User.workspace_id == principal.workspace_id,
            )
        )
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")
        if user.id == principal.user_id:
            raise HTTPException(status_code=409, detail="You cannot delete your own account.")
        _guard_admin_access_change(
            db,
            user,
            principal,
            next_role=user.role,
            next_disabled=True,
        )
        record_activity(
            db,
            workspace_id=principal.workspace_id,
            actor_user_id=principal.user_id,
            entity_type="USER",
            entity_id=user.id,
            action_code="USER_DELETED",
            before=_snapshot(user),
            after=None,
        )
        db.delete(user)
