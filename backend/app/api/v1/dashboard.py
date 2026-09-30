from fastapi import APIRouter, Request

from app.services.auth import CurrentPrincipal
from app.services.dashboard import calculate_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(request: Request, principal: CurrentPrincipal) -> dict[str, object]:
    with request.app.state.database.session() as db:
        data = calculate_dashboard(db, principal.workspace_id)
    return {"data": data, "meta": {}}
