import logging
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response

from app.core.errors import problem_response

logger = logging.getLogger(__name__)


async def safe_request_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("x-request-id", str(uuid4()))[:128]
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request failure", extra={"request_id": request_id})
        response = problem_response(
            status_code=500,
            detail="The server could not complete the request.",
            request_id=request_id,
        )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; "
        "form-action 'self'; object-src 'none'"
    )
    if request.url.path.startswith("/api/v1/auth"):
        response.headers["Cache-Control"] = "no-store"
    return response
