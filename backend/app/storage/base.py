from dataclasses import dataclass
from typing import BinaryIO, Protocol


class StorageError(RuntimeError):
    pass


class StorageKeyError(StorageError):
    pass


class UploadTooLarge(StorageError):
    pass


@dataclass(frozen=True)
class StoredObject:
    key: str
    byte_size: int
    sha256: str
    detected_media_type: str | None


class FileStorage(Protocol):
    def put(self, stream: BinaryIO, *, extension: str, limit: int) -> StoredObject: ...

    def open(self, key: str) -> BinaryIO: ...

    def delete(self, key: str) -> None: ...
