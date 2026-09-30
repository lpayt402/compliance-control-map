import re
import unicodedata
from pathlib import PureWindowsPath
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StoredFile
from app.storage import FileStorage, UploadTooLarge

ALLOWED_MEDIA_TYPES = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
    },
    ".csv": {"text/csv", "text/plain", "application/csv"},
    ".txt": {"text/plain"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".gif": {"image/gif"},
    ".webp": {"image/webp"},
    ".zip": {"application/zip", "application/x-zip-compressed"},
    ".json": {"application/json", "text/plain"},
}
MAGIC_REQUIRED = frozenset(
    {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip"}
)
ZIP_EXTENSIONS = frozenset({".docx", ".xlsx", ".zip"})
TEXT_EXTENSIONS = frozenset({".csv", ".txt", ".json"})
WINDOWS_RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


class UploadValidationError(ValueError):
    pass


class UnsupportedUpload(UploadValidationError):
    pass


def safe_original_filename(filename: str) -> str:
    normalized = unicodedata.normalize("NFC", filename).replace("/", "\\")
    basename = PureWindowsPath(normalized).name
    basename = CONTROL_CHARACTERS.sub("", basename).strip().rstrip(". ")
    if not basename or basename in {".", ".."}:
        raise UploadValidationError("The uploaded filename is empty or unsafe.")
    stem = PureWindowsPath(basename).stem.upper()
    if stem in WINDOWS_RESERVED:
        raise UploadValidationError("The uploaded filename is reserved by the operating system.")
    if len(basename) > 240:
        suffix = PureWindowsPath(basename).suffix
        basename = f"{PureWindowsPath(basename).stem[: 240 - len(suffix)]}{suffix}"
    return basename


def _validate_detected_type(
    storage: FileStorage,
    key: str,
    extension: str,
    declared_media_type: str,
    detected_media_type: str | None,
) -> str:
    allowed_declared = ALLOWED_MEDIA_TYPES[extension]
    if declared_media_type.casefold() not in allowed_declared:
        raise UnsupportedUpload("Declared media type does not match the file extension.")
    if extension in MAGIC_REQUIRED:
        if detected_media_type is None:
            raise UnsupportedUpload("The file signature does not match its extension.")
        if extension in ZIP_EXTENSIONS:
            if detected_media_type not in {"application/zip", "application/x-zip-compressed"}:
                raise UnsupportedUpload("The file signature does not match its extension.")
        elif detected_media_type not in allowed_declared:
            raise UnsupportedUpload("The file signature does not match its extension.")
    if extension in TEXT_EXTENSIONS:
        with storage.open(key) as stream:
            sample = stream.read(64 * 1024)
        if b"\x00" in sample:
            raise UnsupportedUpload("Text uploads cannot contain binary null bytes.")
        try:
            sample.decode("utf-8")
        except UnicodeDecodeError as error:
            raise UnsupportedUpload("Text uploads must use UTF-8 encoding.") from error
        return "application/json" if extension == ".json" else declared_media_type.casefold()
    return detected_media_type or declared_media_type.casefold()


def store_upload(
    session: Session,
    storage: FileStorage,
    *,
    workspace_id: UUID,
    uploaded_by_user_id: UUID | None,
    filename: str,
    declared_media_type: str,
    stream: object,
    limit: int,
    allowed_extensions: set[str],
) -> tuple[StoredFile, bool]:
    safe_name = safe_original_filename(filename)
    extension = PureWindowsPath(safe_name).suffix.casefold()
    if extension not in allowed_extensions or extension not in ALLOWED_MEDIA_TYPES:
        raise UnsupportedUpload("This file extension is not allowed.")
    stored = storage.put(stream, extension=extension, limit=limit)  # type: ignore[arg-type]
    try:
        detected = _validate_detected_type(
            storage,
            stored.key,
            extension,
            declared_media_type,
            stored.detected_media_type,
        )
        existing = session.scalar(
            select(StoredFile).where(
                StoredFile.workspace_id == workspace_id,
                StoredFile.sha256 == stored.sha256,
            )
        )
        if existing is not None:
            storage.delete(stored.key)
            return existing, False
        record = StoredFile(
            workspace_id=workspace_id,
            storage_key=stored.key,
            original_filename=safe_name,
            normalized_extension=extension,
            declared_media_type=declared_media_type.casefold(),
            detected_media_type=detected,
            byte_size=stored.byte_size,
            sha256=stored.sha256,
            uploaded_by_user_id=uploaded_by_user_id,
        )
        session.add(record)
        session.flush()
        return record, True
    except Exception:
        storage.delete(stored.key)
        raise


__all__ = [
    "UnsupportedUpload",
    "UploadTooLarge",
    "UploadValidationError",
    "safe_original_filename",
    "store_upload",
]
