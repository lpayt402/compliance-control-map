from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.permissions import Principal, Role
from app.schemas.requirements import AssessmentUpdate
from app.schemas.resources import TextResourceCreate, TextResourceUpdate
from app.services.activity import activity_data, list_requirement_activity
from app.services.assessments import (
    AssessmentNotFound,
    AssessmentService,
    AssessmentValidationError,
    RequirementFilters,
    RevisionConflict,
    list_requirements,
)
from app.services.auth import CurrentPrincipal, require_role
from app.services.text_resources import (
    TextResourceConflict,
    TextResourceNotFound,
    TextResourceValidationError,
    create_requirement_resource,
    delete_requirement_resource,
    list_requirement_resources,
    resource_data,
    update_requirement_resource,
)

router = APIRouter(prefix="/requirements", tags=["requirements"])
EditorPrincipal = Annotated[Principal, Depends(require_role(Role.EDITOR))]


def _filters(
    search: str | None,
    status: list[str] | None,
    domain: list[str] | None,
    owner: list[UUID] | None,
    assignee: list[UUID] | None,
    applicability: list[str] | None,
    tag: list[str] | None,
    overdue: bool,
    framework: str | None,
    offset: int,
    limit: int,
) -> RequirementFilters:
    return RequirementFilters(
        search=search,
        statuses=tuple(status or ()),
        domains=tuple(domain or ()),
        owners=tuple(owner or ()),
        assignees=tuple(assignee or ()),
        applicability=tuple(applicability or ()),
        tags=tuple(item.casefold() for item in (tag or ())),
        overdue=overdue,
        framework_slug=framework,
        offset=offset,
        limit=limit,
    )


@router.get("")
def requirement_list(
    request: Request,
    principal: CurrentPrincipal,
    search: Annotated[str | None, Query(max_length=200)] = None,
    status: Annotated[list[str] | None, Query()] = None,
    domain: Annotated[list[str] | None, Query()] = None,
    owner: Annotated[list[UUID] | None, Query()] = None,
    assignee: Annotated[list[UUID] | None, Query()] = None,
    applicability: Annotated[list[str] | None, Query()] = None,
    tag: Annotated[list[str] | None, Query()] = None,
    overdue: bool = False,
    framework: Annotated[str | None, Query(max_length=80)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
) -> dict[str, object]:
    filters = _filters(
        search,
        status,
        domain,
        owner,
        assignee,
        applicability,
        tag,
        overdue,
        framework,
        offset,
        limit,
    )
    with request.app.state.database.session() as db:
        data, total = list_requirements(db, principal.workspace_id, filters)
    return {"data": data, "meta": {"total": total, "offset": offset, "limit": limit}}


@router.get("/{requirement_id}")
def requirement_detail(
    request: Request,
    requirement_id: UUID,
    principal: CurrentPrincipal,
) -> dict[str, object]:
    with request.app.state.database.session() as db:
        data, _total = list_requirements(
            db,
            principal.workspace_id,
            RequirementFilters(requirement_id=requirement_id, limit=1),
        )
    if not data:
        raise HTTPException(status_code=404, detail="Requirement not found.")
    return {"data": data[0], "meta": {}}


@router.patch("/{requirement_id}/assessment", response_model=None)
def update_assessment(
    request: Request,
    requirement_id: UUID,
    payload: AssessmentUpdate,
    principal: EditorPrincipal,
) -> dict[str, object] | JSONResponse:
    changes = payload.model_dump(exclude={"revision"}, exclude_unset=True)
    try:
        with request.app.state.database.session() as db:
            AssessmentService(db, principal.workspace_id, principal.user_id).update(
                requirement_id,
                changes,
                expected_revision=payload.revision,
            )
            data, _total = list_requirements(
                db,
                principal.workspace_id,
                RequirementFilters(requirement_id=requirement_id, limit=1),
            )
    except RevisionConflict as conflict:
        return JSONResponse(
            status_code=409,
            media_type="application/problem+json",
            content={
                "type": "https://compliance-control-map.local/problems/revision-conflict",
                "title": "The requirement changed before your update was saved",
                "status": 409,
                "detail": "Reload the current values and apply your change again.",
                "request_id": request.state.request_id,
                "current": {"revision": conflict.current_revision},
            },
        )
    except AssessmentNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except AssessmentValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"data": data[0], "meta": {}}


def _resource_problem(request: Request, conflict: TextResourceConflict) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        media_type="application/problem+json",
        content={
            "type": "https://compliance-control-map.local/problems/revision-conflict",
            "title": "The resource changed before your update was saved",
            "status": 409,
            "detail": "Reload the current values and apply your change again.",
            "request_id": request.state.request_id,
            "current": {"revision": conflict.current_revision},
        },
    )


def _raise_resource_error(error: Exception) -> None:
    if isinstance(error, TextResourceNotFound):
        raise HTTPException(status_code=404, detail=str(error)) from error
    raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/{requirement_id}/notes")
def requirement_notes(
    request: Request,
    requirement_id: UUID,
    principal: CurrentPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            data = [
                resource_data(db, note)
                for note in list_requirement_resources(
                    db, principal.workspace_id, requirement_id
                )
            ]
    except TextResourceNotFound as error:
        _raise_resource_error(error)
    return {"data": data, "meta": {}}


@router.post("/{requirement_id}/notes", status_code=201)
def add_requirement_note(
    request: Request,
    requirement_id: UUID,
    payload: TextResourceCreate,
    principal: EditorPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            note = create_requirement_resource(
                db,
                principal.workspace_id,
                requirement_id,
                principal.user_id,
                payload.model_dump(),
            )
            data = resource_data(db, note)
    except (TextResourceNotFound, TextResourceValidationError) as error:
        _raise_resource_error(error)
    return {"data": data, "meta": {}}


@router.patch("/{requirement_id}/notes/{note_id}", response_model=None)
def edit_requirement_note(
    request: Request,
    requirement_id: UUID,
    note_id: UUID,
    payload: TextResourceUpdate,
    principal: EditorPrincipal,
) -> dict[str, object] | JSONResponse:
    try:
        with request.app.state.database.session() as db:
            note = update_requirement_resource(
                db,
                principal.workspace_id,
                requirement_id,
                note_id,
                principal.user_id,
                payload.model_dump(exclude={"revision"}, exclude_unset=True),
                payload.revision,
            )
            data = resource_data(db, note)
    except TextResourceConflict as conflict:
        return _resource_problem(request, conflict)
    except (TextResourceNotFound, TextResourceValidationError) as error:
        _raise_resource_error(error)
    return {"data": data, "meta": {}}


@router.delete(
    "/{requirement_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def remove_requirement_note(
    request: Request,
    requirement_id: UUID,
    note_id: UUID,
    principal: EditorPrincipal,
    revision: Annotated[int, Query(ge=1)],
) -> Response | JSONResponse:
    try:
        with request.app.state.database.session() as db:
            delete_requirement_resource(
                db,
                principal.workspace_id,
                requirement_id,
                note_id,
                principal.user_id,
                revision,
            )
    except TextResourceConflict as conflict:
        return _resource_problem(request, conflict)
    except (TextResourceNotFound, TextResourceValidationError) as error:
        _raise_resource_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{requirement_id}/activity")
def requirement_activity(
    request: Request,
    requirement_id: UUID,
    principal: CurrentPrincipal,
) -> dict[str, object]:
    with request.app.state.database.session() as db:
        events = list_requirement_activity(db, principal.workspace_id, requirement_id)
        data = [activity_data(db, event) for event in events]
    return {"data": data, "meta": {}}
