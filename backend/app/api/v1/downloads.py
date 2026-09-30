from collections.abc import Iterator
from urllib.parse import quote

from app.storage import FileStorage


def attachment_headers(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}


def stream_stored_file(storage: FileStorage, key: str) -> Iterator[bytes]:
    with storage.open(key) as stream:
        while chunk := stream.read(64 * 1024):
            yield chunk
