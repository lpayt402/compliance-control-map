from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.errors import problem_response

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def liveness() -> dict[str, object]:
    return {"data": {"status": "ok"}, "meta": {}}


class ReadinessDatabase(Protocol):
    def is_ready(self) -> bool: ...


@router.get("/ready", response_model=None)
def readiness(request: Request) -> dict[str, object] | JSONResponse:
    database: ReadinessDatabase = request.app.state.database
    if not database.is_ready():
        return problem_response(
            status_code=503,
            title="Service Unavailable",
            detail="The database is not ready.",
            request_id=request.state.request_id,
        )
    if request.app.state.settings.inference_enabled and getattr(
        request.app.state, "inference_registry_error", None
    ):
        return problem_response(
            status_code=503,
            title="Service Unavailable",
            detail="Installed model-assistance definitions are invalid.",
            request_id=request.state.request_id,
        )
    return {"data": {"status": "ready"}, "meta": {}}
