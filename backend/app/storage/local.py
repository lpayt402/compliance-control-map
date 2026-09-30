import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

import filetype  # type: ignore[import-untyped]

from app.storage.base import StorageKeyError, StoredObject, UploadTooLarge

KEY_PATTERN = re.compile(r"^[a-f0-9]{32}\.[a-z0-9]{1,10}$")
EXTENSION_PATTERN = re.compile(r"^\.[a-z0-9]{1,10}$")
CHUNK_SIZE = 64 * 1024


class LocalFilesystemStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _safe_path(self, key: str) -> Path:
        if not KEY_PATTERN.fullmatch(key):
            raise StorageKeyError("Invalid storage key.")
        root = self.root.resolve()
        candidate = (root / key).resolve()
        if not candidate.is_relative_to(root):
            raise StorageKeyError("Storage key leaves the configured root.")
        return candidate

    def put(self, stream: BinaryIO, *, extension: str, limit: int) -> StoredObject:
        normalized_extension = extension.casefold()
        if not EXTENSION_PATTERN.fullmatch(normalized_extension):
            raise StorageKeyError("Invalid storage extension.")
        self.root.mkdir(parents=True, exist_ok=True)
        root = self.root.resolve()
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=root, prefix=".upload-", delete=False) as target:
                temporary_path = Path(target.name)
                digest = hashlib.sha256()
                byte_size = 0
                while chunk := stream.read(CHUNK_SIZE):
                    byte_size += len(chunk)
                    if byte_size > limit:
                        raise UploadTooLarge(f"Upload exceeds the {limit}-byte limit.")
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            guess = filetype.guess(temporary_path)
            detected = guess.mime if guess else None
            key = f"{uuid4().hex}{normalized_extension}"
            destination = self._safe_path(key)
            os.replace(temporary_path, destination)
            temporary_path = None
            return StoredObject(
                key=key,
                byte_size=byte_size,
                sha256=digest.hexdigest(),
                detected_media_type=detected,
            )
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def open(self, key: str) -> BinaryIO:
        return self._safe_path(key).open("rb")

    def delete(self, key: str) -> None:
        self._safe_path(key).unlink(missing_ok=True)
