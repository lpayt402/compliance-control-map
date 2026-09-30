import hmac
import secrets
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from sqlalchemy import select

from app.core.errors import problem_response
from app.core.permissions import Principal, Role
from app.core.sessions import active_session, csrf_cookie_name, session_cookie_name
from app.models import Workspace

PUBLIC_PATHS = frozenset(
    {
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/api/v1/auth/csrf",
        "/api/v1/auth/login",
    }
)
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _production(request: Request) -> bool:
    return bool(request.app.state.settings.app_env == "production")


def _client_source(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _csrf_is_valid(request: Request) -> bool:
    settings = request.app.state.settings
    origin = request.headers.get("origin")
    if not origin or origin not in settings.allowed_origins:
        return False
    if request.headers.get("sec-fetch-site", "").casefold() == "cross-site":
        return False
    supplied = request.headers.get("x-csrf-token")
    if not supplied:
        return False
    production = _production(request)
    session_token = request.cookies.get(session_cookie_name(production))
    expected: str | None = None
    if session_token:
        with request.app.state.database.session() as db:
            authenticated = active_session(db, session_token)
            if authenticated:
                expected = authenticated[0].csrf_secret
    if expected is None:
        expected = request.cookies.get(csrf_cookie_name(production))
    return expected is not None and hmac.compare_digest(supplied, expected)


def _load_principal(request: Request) -> Principal | None:
    settings = request.app.state.settings
    if settings.auth_mode == "disabled":
        with request.app.state.database.session() as db:
            workspace = db.scalar(select(Workspace).where(Workspace.slug == "default"))
        if workspace is None:
            return None
        return Principal(
            workspace_id=workspace.id,
            user_id=None,
            role=Role.ADMIN,
            display_name="Local administrator",
            auth_disabled=True,
        )
    token = request.cookies.get(session_cookie_name(_production(request)))
    with request.app.state.database.session() as db:
        authenticated = active_session(db, token)
        if authenticated is None:
            return None
        _record, user = authenticated
        return Principal(
            workspace_id=user.workspace_id,
            user_id=user.id,
            role=Role(user.role),
            display_name=user.display_name,
        )


async def request_security_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    content_type = request.headers.get("content-type", "").casefold()
    if request.method in UNSAFE_METHODS and content_type.startswith("multipart/form-data"):
        raw_length = request.headers.get("content-length")
        try:
            content_length = int(raw_length) if raw_length is not None else 0
        except ValueError:
            content_length = 0
        if content_length <= 0:
            return problem_response(
                status_code=411,
                detail="A valid Content-Length header is required for uploads.",
                request_id=request.state.request_id,
            )
        if content_length > request.app.state.settings.max_upload_bytes + 256 * 1024:
            return problem_response(
                status_code=413,
                detail="The upload is larger than this installation permits.",
                request_id=request.state.request_id,
            )
    if (
        request.url.path.startswith("/api/v1")
        and request.method in UNSAFE_METHODS
        and not _csrf_is_valid(request)
    ):
        return problem_response(
            status_code=403,
            detail="Request verification failed.",
            request_id=request.state.request_id,
        )

    if request.url.path.startswith("/api/v1") and request.url.path not in PUBLIC_PATHS:
        principal = _load_principal(request)
        if principal is None:
            return problem_response(
                status_code=401,
                detail="Authentication required.",
                request_id=request.state.request_id,
            )
        request.state.principal = principal
    request.state.client_source = _client_source(request)
    return await call_next(request)


def issue_preauth_csrf() -> str:
    return secrets.token_urlsafe(32)
