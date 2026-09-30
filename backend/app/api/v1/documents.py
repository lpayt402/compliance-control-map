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
    DocumentLinkBatch,
    RequirementMappingBatch,
)
from app.services.auth import CurrentPrincipal, require_role
from app.services.documents import (
    create_document,
    document_data,
    documents_for_control,
    documents_for_requirement,
    get_document,
    list_documents,
    map_document_controls,
    map_document_requirements,
    unmap_document_control,
    unmap_document_requirement,
)
from app.services.libraries import LibraryNotFound, LibraryValidationError
from app.services.uploads import UnsupportedUpload, UploadTooLarge, UploadValidationError

router = APIRouter(prefix="/documents", tags=["documents"])
requirement_router = APIRouter(prefix="/requirements", tags=["documents"])
control_router = APIRouter(prefix="/controls", tags=["documents"])
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
def documents(request: Request, principal: CurrentPrincipal) -> dict[str, object]:
    with request.app.state.database.session() as db:
        data = list_documents(db, principal.workspace_id)
    return {"data": data, "meta": {"total": len(data)}}


@router.post("", status_code=201)
def upload_document(
    request: Request,
    principal: EditorPrincipal,
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form(min_length=1, max_length=300)],
    document_type: Annotated[
        str,
        Form(pattern="^(POLICY|STANDARD|PROCEDURE|PLAN|GUIDELINE|OTHER)$"),
    ] = "OTHER",
    description: Annotated[str, Form(max_length=20_000)] = "",
    version: Annotated[str, Form(max_length=80)] = "",
    effective_date: Annotated[date | None, Form()] = None,
    owner_user_id: Annotated[UUID | None, Form()] = None,
    notes: Annotated[str, Form(max_length=20_000)] = "",
    requirement_ids: Annotated[list[UUID] | None, Form()] = None,
    control_ids: Annotated[list[UUID] | None, Form()] = None,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            document = create_document(
                db,
                request.app.state.storage,
                workspace_id=principal.workspace_id,
                actor_user_id=principal.user_id,
                name=name,
                document_type=document_type,
                description=description,
                version=version,
                effective_date=effective_date,
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
            data = document_data(db, document)
    except (
        LibraryNotFound,
        LibraryValidationError,
        UploadValidationError,
        UploadTooLarge,
    ) as error:
        _raise_library_error(error)
    return {"data": data, "meta": {}}


@router.get("/{document_id}")
def document_detail(
    request: Request,
    document_id: UUID,
    principal: CurrentPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            data = document_data(db, get_document(db, principal.workspace_id, document_id))
    except LibraryNotFound as error:
        _raise_library_error(error)
    return {"data": data, "meta": {}}


@router.post("/{document_id}/requirements")
def add_document_requirements(
    request: Request,
    document_id: UUID,
    payload: RequirementMappingBatch,
    principal: EditorPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            document = map_document_requirements(
                db,
                principal.workspace_id,
                principal.user_id,
                document_id,
                payload.requirement_ids,
                payload.rationale,
            )
            data = document_data(db, document)
    except (LibraryNotFound, LibraryValidationError) as error:
        _raise_library_error(error)
    return {"data": data, "meta": {}}


@router.post("/{document_id}/controls")
def add_document_controls(
    request: Request,
    document_id: UUID,
    payload: ControlMappingBatch,
    principal: EditorPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            document = map_document_controls(
                db,
                principal.workspace_id,
                principal.user_id,
                document_id,
                payload.control_ids,
            )
            data = document_data(db, document)
    except (LibraryNotFound, LibraryValidationError) as error:
        _raise_library_error(error)
    return {"data": data, "meta": {}}


@router.get("/{document_id}/download")
def download_document(
    request: Request,
    document_id: UUID,
    principal: CurrentPrincipal,
) -> StreamingResponse:
    try:
        with request.app.state.database.session() as db:
            document = get_document(db, request.state.principal.workspace_id, document_id)
            stored_file = db.scalar(
                select(StoredFile).where(
                    StoredFile.id == document.stored_file_id,
                    StoredFile.workspace_id == principal.workspace_id,
                )
            )
            if stored_file is None:
                raise LibraryNotFound("Stored document file not found.")
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


@requirement_router.get("/{requirement_id}/documents")
def requirement_documents(
    request: Request,
    requirement_id: UUID,
    principal: CurrentPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            data = documents_for_requirement(db, principal.workspace_id, requirement_id)
    except LibraryNotFound as error:
        _raise_library_error(error)
    return {"data": data, "meta": {"total": len(data)}}


@requirement_router.post("/{requirement_id}/documents")
def add_requirement_documents(
    request: Request,
    requirement_id: UUID,
    payload: DocumentLinkBatch,
    principal: EditorPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            for document_id in payload.document_ids:
                map_document_requirements(
                    db,
                    principal.workspace_id,
                    principal.user_id,
                    document_id,
                    [requirement_id],
                    payload.rationale,
                )
            data = documents_for_requirement(db, principal.workspace_id, requirement_id)
    except (LibraryNotFound, LibraryValidationError) as error:
        _raise_library_error(error)
    return {"data": data, "meta": {"total": len(data)}}


@requirement_router.delete(
    "/{requirement_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_requirement_document(
    request: Request,
    requirement_id: UUID,
    document_id: UUID,
    principal: EditorPrincipal,
) -> Response:
    try:
        with request.app.state.database.session() as db:
            unmap_document_requirement(
                db,
                principal.workspace_id,
                principal.user_id,
                requirement_id,
                document_id,
            )
    except (LibraryNotFound, LibraryValidationError) as error:
        _raise_library_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@control_router.get("/{control_id}/documents")
def control_documents(
    request: Request,
    control_id: UUID,
    principal: CurrentPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            data = documents_for_control(db, principal.workspace_id, control_id)
    except (LibraryNotFound, LibraryValidationError) as error:
        _raise_library_error(error)
    return {"data": data, "meta": {"total": len(data)}}


@control_router.post("/{control_id}/documents")
def add_control_documents(
    request: Request,
    control_id: UUID,
    payload: DocumentLinkBatch,
    principal: EditorPrincipal,
) -> dict[str, object]:
    try:
        with request.app.state.database.session() as db:
            for document_id in payload.document_ids:
                map_document_controls(
                    db,
                    principal.workspace_id,
                    principal.user_id,
                    document_id,
                    [control_id],
                )
            data = documents_for_control(db, principal.workspace_id, control_id)
    except (LibraryNotFound, LibraryValidationError) as error:
        _raise_library_error(error)
    return {"data": data, "meta": {"total": len(data)}}


@control_router.delete(
    "/{control_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_control_document(
    request: Request,
    control_id: UUID,
    document_id: UUID,
    principal: EditorPrincipal,
) -> Response:
    try:
        with request.app.state.database.session() as db:
            unmap_document_control(
                db,
                principal.workspace_id,
                principal.user_id,
                control_id,
                document_id,
            )
    except (LibraryNotFound, LibraryValidationError) as error:
        _raise_library_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
