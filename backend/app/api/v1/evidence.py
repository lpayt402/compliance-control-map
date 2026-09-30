from datetime import date
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.v1.downloads import attachment_headers, stream_stored_file
from app.core.permissions import Principal, Role
from app.models import StoredFile
from app.schemas.libraries import (
    ControlMappingBatch,
    EvidenceLinkBatch,
    RequirementMappingBatch,
)
from app.services.auth import CurrentPrincipal, require_role
from app.services.evidence import (
    create_evidence,
    evidence_data,
    evidence_for_control,
    evidence_for_requirement,
    get_evidence,
    list_evidence,
    map_evidence_controls,
    map_evidence_requirements,
    unmap_evidence_control,
    unmap_evidence_requirement,
)
from app.services.libraries import LibraryNotFound, LibraryValidationError
from app.services.uploads import UnsupportedUpload, UploadTooLarge, UploadValidationError

router = APIRouter(prefix="/evidence", tags=["evidence"])
requirement_router = APIRouter(prefix="/requirements", tags=["evidence"])
control_router = APIRouter(prefix="/controls", tags=["evidence"])
EditorPrincipal = Annotated[Principal, Depends(require_role(Role.EDITOR))]


def _raise_library_error(error: Exception) -> NoReturn:
    if isinstance(error, LibraryNotFound):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, UploadTooLarge):
        raise HTTPException(status_code=413, detail=str(error)) from error
    if isinstance(error, UnsupportedUpload):
        raise HTTPException(status_code=415, detail=str(error)) from error
    raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("")
def evidence_list(request: Request, principal: CurrentPrincipal) -> dict[str, object]:
    with request.app.state.database.session() as db:
        data = list_evidence(db, principal.workspace_id)
    return {"data": data, "meta": {"total": len(data)}}


@router.post("", status_code=201)
def upload_evidence(
    request: Request,
    principal: EditorPrincipal,
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form(min_length=1, max_length=300)],
    description: Annotated[str, Form(max_length=20_000)] = "",
    evidence_date: Annotated[date | None, Form()] = None,
    owner_user_id: Annotated[UUID | None, Form()] = None,
    notes: Annotated[str, Form(max_length=20_000)] = "",
    requirement_ids: Annotated[list[UUID] | None, Form()] = None,
    control_ids: Annotated[list[UUID] | None, Form()] = None,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            evidence = create_evidence(
                db,
                request.app.state.storage,
                workspace_id=principal.workspace_id,
                actor_user_id=principal.user_id,
                name=name,
                description=description,
                evidence_date=evidence_date,
                owner_user_id=owner_user_id,
                notes=notes,
                requirement_ids=requirement_ids or [],
                control_ids=control_ids or [],
                filename=file.filename or "upload",
                declared_media_type=file.content_type or "application/octet-stream",
                stream=file.file,
                limit=request.app.state.settings.max_upload_bytes,
                allowed_extensions=set(request.app.state.settings.allowed_upload_extensions),
            )
            data = evidence_data(db, evidence)
    except (
        LibraryNotFound,
        LibraryValidationError,
        UploadValidationError,
        UploadTooLarge,
    ) as error:
        _raise_library_error(error)
    return {"data": data, "meta": {}}


@router.get("/{evidence_id}")
def evidence_detail(
    request: Request,
    evidence_id: UUID,
    principal: CurrentPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            data = evidence_data(db, get_evidence(db, principal.workspace_id, evidence_id))
    except LibraryNotFound as error:
        _raise_library_error(error)
    return {"data": data, "meta": {}}


@router.post("/{evidence_id}/requirements")
def add_evidence_requirements(
    request: Request,
    evidence_id: UUID,
    payload: RequirementMappingBatch,
    principal: EditorPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            evidence = map_evidence_requirements(
                db,
                principal.workspace_id,
                principal.user_id,
                evidence_id,
                payload.requirement_ids,
                payload.rationale,
            )
            data = evidence_data(db, evidence)
    except (LibraryNotFound, LibraryValidationError) as error:
        _raise_library_error(error)
    return {"data": data, "meta": {}}


@router.post("/{evidence_id}/controls")
def add_evidence_controls(
    request: Request,
    evidence_id: UUID,
    payload: ControlMappingBatch,
    principal: EditorPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            evidence = map_evidence_controls(
                db,
                principal.workspace_id,
                principal.user_id,
                evidence_id,
                payload.control_ids,
            )
            data = evidence_data(db, evidence)
    except (LibraryNotFound, LibraryValidationError) as error:
        _raise_library_error(error)
    return {"data": data, "meta": {}}


@router.get("/{evidence_id}/download")
def download_evidence(
    request: Request,
    evidence_id: UUID,
    principal: CurrentPrincipal,
) -> StreamingResponse:
    try:
        with request.app.state.database.session() as db:
            evidence = get_evidence(db, principal.workspace_id, evidence_id)
            stored_file = db.scalar(
                select(StoredFile).where(
                    StoredFile.id == evidence.stored_file_id,
                    StoredFile.workspace_id == principal.workspace_id,
                )
            )
            if stored_file is None:
                raise LibraryNotFound("Stored evidence file not found.")
            key = stored_file.storage_key
            filename = stored_file.original_filename
            media_type = stored_file.detected_media_type
    except LibraryNotFound as error:
        _raise_library_error(error)
    return StreamingResponse(
        stream_stored_file(request.app.state.storage, key),
        media_type=media_type,
        headers=attachment_headers(filename),
    )


@requirement_router.get("/{requirement_id}/evidence")
def requirement_evidence(
    request: Request,
    requirement_id: UUID,
    principal: CurrentPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            data = evidence_for_requirement(db, principal.workspace_id, requirement_id)
    except LibraryNotFound as error:
        _raise_library_error(error)
    return {"data": data, "meta": {"total": len(data)}}


@requirement_router.post("/{requirement_id}/evidence")
def add_requirement_evidence(
    request: Request,
    requirement_id: UUID,
    payload: EvidenceLinkBatch,
    principal: EditorPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            for evidence_id in payload.evidence_ids:
                map_evidence_requirements(
                    db,
                    principal.workspace_id,
                    principal.user_id,
                    evidence_id,
                    [requirement_id],
                    payload.rationale,
                )
            data = evidence_for_requirement(db, principal.workspace_id, requirement_id)
    except (LibraryNotFound, LibraryValidationError) as error:
        _raise_library_error(error)
    return {"data": data, "meta": {"total": len(data)}}


@requirement_router.delete(
    "/{requirement_id}/evidence/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_requirement_evidence(
    request: Request,
    requirement_id: UUID,
    evidence_id: UUID,
    principal: EditorPrincipal,
) -> Response:
    try:
        with request.app.state.database.session() as db:
            unmap_evidence_requirement(
                db,
                principal.workspace_id,
                principal.user_id,
                requirement_id,
                evidence_id,
            )
    except (LibraryNotFound, LibraryValidationError) as error:
        _raise_library_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@control_router.get("/{control_id}/evidence")
def control_evidence(
    request: Request,
    control_id: UUID,
    principal: CurrentPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            data = evidence_for_control(db, principal.workspace_id, control_id)
    except (LibraryNotFound, LibraryValidationError) as error:
        _raise_library_error(error)
    return {"data": data, "meta": {"total": len(data)}}


@control_router.post("/{control_id}/evidence")
def add_control_evidence(
    request: Request,
    control_id: UUID,
    payload: EvidenceLinkBatch,
    principal: EditorPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            for evidence_id in payload.evidence_ids:
                map_evidence_controls(
                    db,
                    principal.workspace_id,
                    principal.user_id,
                    evidence_id,
                    [control_id],
                )
            data = evidence_for_control(db, principal.workspace_id, control_id)
    except (LibraryNotFound, LibraryValidationError) as error:
        _raise_library_error(error)
    return {"data": data, "meta": {"total": len(data)}}


@control_router.delete(
    "/{control_id}/evidence/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_control_evidence(
    request: Request,
    control_id: UUID,
    evidence_id: UUID,
    principal: EditorPrincipal,
) -> Response:
    try:
        with request.app.state.database.session() as db:
            unmap_evidence_control(
                db,
                principal.workspace_id,
                principal.user_id,
                control_id,
                evidence_id,
            )
    except (LibraryNotFound, LibraryValidationError) as error:
        _raise_library_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
