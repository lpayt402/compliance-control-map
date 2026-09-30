from http import HTTPStatus

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def problem_response(
    *,
    status_code: int,
    title: str | None = None,
    detail: str,
    request_id: str,
    problem_type: str = "about:blank",
) -> JSONResponse:
    resolved_title = title or HTTPStatus(status_code).phrase
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content={
            "type": problem_type,
            "title": resolved_title,
            "status": status_code,
            "detail": detail,
            "request_id": request_id,
        },
    )


async def safe_validation_error(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """Keep useful validation locations/messages without reflecting hostile input."""

    if not isinstance(exc, RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": "Invalid request."})
    errors = [
        {
            "type": item.get("type", "value_error"),
            "loc": item.get("loc", ()),
            "msg": item.get("msg", "Invalid value."),
        }
        for item in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})
