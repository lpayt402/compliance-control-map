from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.permissions import Principal, Role
from app.schemas.crosswalks import RequirementMappingCreate
from app.services.auth import CurrentPrincipal, require_role
from app.services.crosswalks import (
    CrosswalkConflict,
    CrosswalkNotFound,
    create_mapping,
    delete_mapping,
    list_mappings,
    mapping_data,
)

router = APIRouter(prefix="/requirement-mappings", tags=["crosswalks"])
requirement_router = APIRouter(prefix="/requirements", tags=["crosswalks"])
EditorPrincipal = Annotated[Principal, Depends(require_role(Role.EDITOR))]


@router.get("")
def mappings(request: Request, principal: CurrentPrincipal) -> dict[str, object]:
    with request.app.state.database.session() as db:
        data = list_mappings(db, principal.workspace_id)
    return {"data": data, "meta": {"total": len(data)}}


@router.post("", status_code=201)
def add_mapping(
    request: Request,
    payload: RequirementMappingCreate,
    principal: EditorPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            mapping = create_mapping(
                db,
                principal.workspace_id,
                principal.user_id,
                **payload.model_dump(),
            )
            data = mapping_data(db, mapping)
    except CrosswalkNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except CrosswalkConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"data": data, "meta": {}}


@router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_mapping(
    request: Request,
    mapping_id: UUID,
    principal: EditorPrincipal,
) -> Response:
    try:
        with request.app.state.database.session() as db:
            delete_mapping(
                db,
                principal.workspace_id,
                principal.user_id,
                mapping_id,
            )
    except CrosswalkNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@requirement_router.get("/{requirement_id}/mappings")
def requirement_mappings(
    request: Request,
    requirement_id: UUID,
    principal: CurrentPrincipal,
) -> dict[str, object]:
    with request.app.state.database.session() as db:
        data = list_mappings(db, principal.workspace_id, requirement_id)
    return {"data": data, "meta": {"total": len(data)}}
