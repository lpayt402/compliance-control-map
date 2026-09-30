from fastapi import APIRouter, Request

from app.services.frameworks import list_frameworks

router = APIRouter(prefix="/frameworks", tags=["frameworks"])


@router.get("")
def framework_list(request: Request) -> dict[str, object]:
    with request.app.state.database.session() as session:
        data = [item.model_dump(mode="json") for item in list_frameworks(session)]
    return {"data": data, "meta": {}}
