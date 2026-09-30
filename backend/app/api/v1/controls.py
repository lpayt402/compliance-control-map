from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.permissions import Principal, Role
from app.schemas.controls import ControlCreate, ControlUpdate, RequirementControlCreate
from app.schemas.resources import TextResourceCreate, TextResourceUpdate
from app.services.activity import activity_data, list_control_activity
from app.services.auth import CurrentPrincipal, require_role
from app.services.controls import (
    ControlConflict,
    ControlNotFound,
    ControlValidationError,
    control_data,
    create_control,
    get_control,
    link_control,
    list_controls,
    list_requirement_controls,
    unlink_control,
    update_control,
)
from app.services.text_resources import (
    TextResourceConflict,
    TextResourceNotFound,
    TextResourceValidationError,
    create_control_resource,
    delete_control_resource,
    list_control_resources,
    resource_data,
    update_control_resource,
)

router = APIRouter(prefix="/controls", tags=["controls"])
mapping_router = APIRouter(prefix="/requirements", tags=["controls"])
EditorPrincipal = Annotated[Principal, Depends(require_role(Role.EDITOR))]


def _raise_control_error(error: Exception) -> None:
    if isinstance(error, ControlNotFound):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, ControlConflict):
        raise HTTPException(status_code=409, detail=str(error)) from error
    raise HTTPException(status_code=422, detail=str(error)) from error


def _revision_problem(
    request: Request,
    title: str,
    current_revision: int,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        media_type="application/problem+json",
        content={
            "type": "https://compliance-control-map.local/problems/revision-conflict",
            "title": title,
            "status": 409,
            "detail": "Reload the current values and apply your change again.",
            "request_id": request.state.request_id,
            "current": {"revision": current_revision},
        },
    )


def _raise_resource_error(error: Exception) -> None:
    if isinstance(error, TextResourceNotFound):
        raise HTTPException(status_code=404, detail=str(error)) from error
    raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("")
def controls(request: Request, principal: CurrentPrincipal) -> dict[str, object]:
    with request.app.state.database.session() as db:
        data = list_controls(db, principal.workspace_id)
    return {"data": data, "meta": {"total": len(data)}}


@router.post("", status_code=201)
def add_control(
    request: Request,
    payload: ControlCreate,
    principal: EditorPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            control = create_control(
                db,
                principal.workspace_id,
                principal.user_id,
                payload.model_dump(),
            )
            data = control_data(db, control)
    except (ControlNotFound, ControlConflict, ControlValidationError) as error:
        _raise_control_error(error)
    return {"data": data, "meta": {}}


@router.get("/{control_id}")
def control_detail(
    request: Request,
    control_id: UUID,
    principal: CurrentPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            data = control_data(db, get_control(db, principal.workspace_id, control_id))
    except ControlNotFound as error:
        _raise_control_error(error)
    return {"data": data, "meta": {}}


@router.patch("/{control_id}", response_model=None)
def change_control(
    request: Request,
    control_id: UUID,
    payload: ControlUpdate,
    principal: EditorPrincipal,
) -> dict[str, object] | JSONResponse:
    values = payload.model_dump(exclude={"revision"}, exclude_unset=True)
    try:
        with request.app.state.database.session() as db:
            control = update_control(
                db,
                principal.workspace_id,
                principal.user_id,
                control_id,
                values,
                payload.revision,
            )
            data = control_data(db, control)
    except ControlConflict as error:
        if error.current_revision is not None:
            return _revision_problem(
                request,
                "The control changed before your update was saved",
                error.current_revision,
            )
        _raise_control_error(error)
    except (ControlNotFound, ControlValidationError) as error:
        _raise_control_error(error)
    return {"data": data, "meta": {}}


@router.get("/{control_id}/notes")
def control_notes(
    request: Request,
    control_id: UUID,
    principal: CurrentPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            data = [
                resource_data(db, resource)
                for resource in list_control_resources(
                    db, principal.workspace_id, control_id
                )
            ]
    except TextResourceNotFound as error:
        _raise_resource_error(error)
    return {"data": data, "meta": {"total": len(data)}}


@router.post("/{control_id}/notes", status_code=201)
def add_control_note(
    request: Request,
    control_id: UUID,
    payload: TextResourceCreate,
    principal: EditorPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            resource = create_control_resource(
                db,
                principal.workspace_id,
                control_id,
                principal.user_id,
                payload.model_dump(),
            )
            data = resource_data(db, resource)
    except (TextResourceNotFound, TextResourceValidationError) as error:
        _raise_resource_error(error)
    return {"data": data, "meta": {}}


@router.patch("/{control_id}/notes/{note_id}", response_model=None)
def edit_control_note(
    request: Request,
    control_id: UUID,
    note_id: UUID,
    payload: TextResourceUpdate,
    principal: EditorPrincipal,
) -> dict[str, object] | JSONResponse:
    try:
        with request.app.state.database.session() as db:
            resource = update_control_resource(
                db,
                principal.workspace_id,
                control_id,
                note_id,
                principal.user_id,
                payload.model_dump(exclude={"revision"}, exclude_unset=True),
                payload.revision,
            )
            data = resource_data(db, resource)
    except TextResourceConflict as conflict:
        return _revision_problem(
            request,
            "The resource changed before your update was saved",
            conflict.current_revision,
        )
    except (TextResourceNotFound, TextResourceValidationError) as error:
        _raise_resource_error(error)
    return {"data": data, "meta": {}}


@router.delete(
    "/{control_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def remove_control_note(
    request: Request,
    control_id: UUID,
    note_id: UUID,
    principal: EditorPrincipal,
    revision: Annotated[int, Query(ge=1)],
) -> Response | JSONResponse:
    try:
        with request.app.state.database.session() as db:
            delete_control_resource(
                db,
                principal.workspace_id,
                control_id,
                note_id,
                principal.user_id,
                revision,
            )
    except TextResourceConflict as conflict:
        return _revision_problem(
            request,
            "The resource changed before your update was saved",
            conflict.current_revision,
        )
    except (TextResourceNotFound, TextResourceValidationError) as error:
        _raise_resource_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{control_id}/activity")
def control_activity(
    request: Request,
    control_id: UUID,
    principal: CurrentPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            get_control(db, principal.workspace_id, control_id)
            events = list_control_activity(db, principal.workspace_id, control_id)
            data = [activity_data(db, event) for event in events]
    except ControlNotFound as error:
        _raise_control_error(error)
    return {"data": data, "meta": {}}


@mapping_router.get("/{requirement_id}/controls")
def requirement_controls(
    request: Request,
    requirement_id: UUID,
    principal: CurrentPrincipal,
) -> dict[str, object]:
    with request.app.state.database.session() as db:
        data = list_requirement_controls(db, principal.workspace_id, requirement_id)
    return {"data": data, "meta": {"total": len(data)}}


@mapping_router.post("/{requirement_id}/controls", status_code=201)
def add_requirement_control(
    request: Request,
    requirement_id: UUID,
    payload: RequirementControlCreate,
    principal: EditorPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            mapping = link_control(
                db,
                principal.workspace_id,
                principal.user_id,
                requirement_id,
                payload.control_id,
                payload.coverage,
                payload.rationale,
            )
            data = {
                "id": str(mapping.id),
                "requirement_id": str(mapping.requirement_id),
                "control_id": str(mapping.control_id),
                "coverage": mapping.coverage,
                "rationale": mapping.rationale,
            }
    except (ControlNotFound, ControlConflict, ControlValidationError) as error:
        _raise_control_error(error)
    return {"data": data, "meta": {}}


@mapping_router.delete(
    "/{requirement_id}/controls/{control_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_requirement_control(
    request: Request,
    requirement_id: UUID,
    control_id: UUID,
    principal: EditorPrincipal,
) -> Response:
    try:
        with request.app.state.database.session() as db:
            unlink_control(
                db,
                principal.workspace_id,
                principal.user_id,
                requirement_id,
                control_id,
            )
    except (ControlNotFound, ControlConflict, ControlValidationError) as error:
        _raise_control_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
