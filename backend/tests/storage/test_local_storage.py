from io import BytesIO
from pathlib import Path

import pytest

from app.storage.local import LocalFilesystemStorage, StorageKeyError, UploadTooLarge


def test_local_storage_uses_random_key_hashes_content_and_reopens_safely(
    tmp_path: Path,
) -> None:
    storage = LocalFilesystemStorage(tmp_path)

    stored = storage.put(BytesIO(b"evidence bytes"), extension=".txt", limit=100)

    assert stored.key.endswith(".txt")
    assert "evidence" not in stored.key
    assert len(stored.sha256) == 64
    with storage.open(stored.key) as stream:
        assert stream.read() == b"evidence bytes"


def test_local_storage_rejects_traversal_keys_and_cleans_oversized_temp_files(
    tmp_path: Path,
) -> None:
    storage = LocalFilesystemStorage(tmp_path)

    with pytest.raises(StorageKeyError):
        storage.open("../outside.txt")
    with pytest.raises(UploadTooLarge):
        storage.put(BytesIO(b"too many bytes"), extension=".txt", limit=4)

    assert list(tmp_path.iterdir()) == []
