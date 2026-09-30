from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response

from app.core.permissions import Principal, Role
from app.services.auth import require_role
from app.services.exports import (
    ArchiveValidationError,
    RestoreTargetNotEmpty,
    create_workspace_export,
    restore_workspace_export,
)

router = APIRouter(prefix="/exports", tags=["exports"])
AdminPrincipal = Annotated[Principal, Depends(require_role(Role.ADMIN))]


@router.post("")
def export_workspace(request: Request, principal: AdminPrincipal) -> Response:
    with request.app.state.database.session() as db:
        archive = create_workspace_export(db, request.app.state.storage, principal.workspace_id)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return Response(
        archive,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="compliance-control-backup-{timestamp}.zip"'
            )
        },
    )


@router.post("/restore", status_code=204)
def restore_workspace(
    request: Request,
    principal: AdminPrincipal,
    file: Annotated[UploadFile, File()],
) -> Response:
    archive = file.file.read(request.app.state.settings.max_upload_bytes + 1)
    if len(archive) > request.app.state.settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Restore archive exceeds the upload limit.")
    try:
        with request.app.state.database.session() as db:
            restore_workspace_export(
                db,
                request.app.state.storage,
                principal.workspace_id,
                archive,
            )
    except RestoreTargetNotEmpty as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ArchiveValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return Response(status_code=204)
