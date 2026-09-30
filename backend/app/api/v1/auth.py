from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.passwords import PasswordPolicyError, hash_password, verify_password
from app.core.permissions import Principal, Role
from app.core.request_security import issue_preauth_csrf
from app.core.sessions import (
    active_session,
    create_session,
    csrf_cookie_name,
    revoke_session,
    revoke_user_sessions,
    session_cookie_name,
)
from app.models import User
from app.schemas.auth import LoginRequest, PasswordChangeRequest, UserResponse
from app.services.activity import record_activity
from app.services.auth import CurrentPrincipal, authenticate_password

router = APIRouter(prefix="/auth", tags=["authentication"])


def _production(request: Request) -> bool:
    return bool(request.app.state.settings.app_env == "production")


def _user_response(principal: Principal) -> dict[str, object]:
    if principal.user_id is None:
        return {
            "id": None,
            "email": None,
            "display_name": principal.display_name,
            "role": principal.role,
        }
    return {
        "id": principal.user_id,
        "email": None,
        "display_name": principal.display_name,
        "role": principal.role,
    }


@router.get("/csrf")
def csrf(request: Request, response: Response) -> dict[str, object]:
    production = _production(request)
    token: str | None = None
    session_token = request.cookies.get(session_cookie_name(production))
    if session_token:
        with request.app.state.database.session() as db:
            authenticated = active_session(db, session_token)
            if authenticated:
                token = authenticated[0].csrf_secret
    if token is None:
        token = issue_preauth_csrf()
    response.set_cookie(
        csrf_cookie_name(production),
        token,
        secure=production,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=3600,
    )
    return {"data": {"csrf_token": token}, "meta": {}}


@router.post("/login")
def login(request: Request, response: Response, payload: LoginRequest) -> dict[str, object]:
    source = request.state.client_source
    throttle = request.app.state.login_throttle
    if throttle.is_blocked(source, str(payload.email)):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    with request.app.state.database.session() as db:
        user = authenticate_password(db, str(payload.email), payload.password)
        if user is None:
            throttle.record_failure(source, str(payload.email))
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        created = create_session(db, user)
        user_data = UserResponse(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=Role(user.role),
        ).model_dump(mode="json")
    throttle.clear(source, str(payload.email))
    production = _production(request)
    response.set_cookie(
        session_cookie_name(production),
        created.token,
        secure=production,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=12 * 60 * 60,
    )
    response.delete_cookie(csrf_cookie_name(production), path="/")
    return {"data": {"user": user_data, "csrf_token": created.csrf_token}, "meta": {}}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> None:
    production = _production(request)
    token = request.cookies.get(session_cookie_name(production))
    with request.app.state.database.session() as db:
        authenticated = active_session(db, token)
        if authenticated:
            revoke_session(authenticated[0])
    response.delete_cookie(session_cookie_name(production), path="/")
    response.delete_cookie(csrf_cookie_name(production), path="/")
    response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    request: Request,
    response: Response,
    payload: PasswordChangeRequest,
    principal: CurrentPrincipal,
) -> None:
    if principal.user_id is None:
        raise HTTPException(status_code=409, detail="Local no-login mode has no password.")
    with request.app.state.database.session() as db:
        user = db.get(User, principal.user_id)
        if (
            user is None
            or user.password_hash is None
            or not verify_password(payload.current_password, user.password_hash)
        ):
            raise HTTPException(status_code=401, detail="Current password is incorrect.")
        try:
            user.password_hash = hash_password(payload.new_password)
        except PasswordPolicyError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        record_activity(
            db,
            workspace_id=principal.workspace_id,
            actor_user_id=principal.user_id,
            entity_type="USER",
            entity_id=user.id,
            action_code="PASSWORD_CHANGED",
            before=None,
            after=None,
        )
        revoke_user_sessions(db, user.id)

    production = _production(request)
    response.delete_cookie(session_cookie_name(production), path="/")
    response.delete_cookie(csrf_cookie_name(production), path="/")
    response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'


@router.get("/me")
def me(principal: CurrentPrincipal) -> dict[str, object]:
    return {"data": _user_response(principal), "meta": {}}
