import pytest
from fastapi.testclient import TestClient

from app.services.uploads import UploadValidationError, safe_original_filename
from tests.api.test_requirements import _csrf_headers


def test_upload_sanitizes_name_and_uses_random_storage_key(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    response = client.post(
        "/api/v1/documents",
        headers=_csrf_headers(client),
        data={"name": "Access Control Policy", "document_type": "POLICY"},
        files={"file": ("..\\Access Policy.txt", b"demo policy", "text/plain")},
    )

    assert response.status_code == 201
    stored = response.json()["data"]["file"]
    assert stored["original_filename"] == "Access Policy.txt"
    assert "Access Policy" not in stored["storage_key"]
    storage_root = client.app.state.settings.storage_root
    assert (storage_root / stored["storage_key"]).read_bytes() == b"demo policy"


def test_upload_rejects_unsupported_mismatched_and_oversized_files(
    requirements_client: TestClient,
) -> None:
    client = requirements_client
    headers = _csrf_headers(client)
    unsupported = client.post(
        "/api/v1/evidence",
        headers=headers,
        data={"name": "Executable"},
        files={"file": ("payload.exe", b"MZ-not-really", "application/octet-stream")},
    )
    mismatch = client.post(
        "/api/v1/evidence",
        headers=headers,
        data={"name": "Fake PDF"},
        files={"file": ("review.pdf", b"plain text", "application/pdf")},
    )
    client.app.state.settings.max_upload_bytes = 4
    oversized = client.post(
        "/api/v1/evidence",
        headers=headers,
        data={"name": "Too large"},
        files={"file": ("review.txt", b"more than four bytes", "text/plain")},
    )

    assert unsupported.status_code == 415
    assert mismatch.status_code == 415
    assert oversized.status_code == 413
    assert list(client.app.state.settings.storage_root.iterdir()) == []


def test_upload_requires_content_length_before_multipart_parsing(
    requirements_client: TestClient,
) -> None:
    response = requirements_client.post(
        "/api/v1/evidence",
        headers={**_csrf_headers(requirements_client), "Content-Length": "0"},
        data={"name": "Missing length"},
        files={"file": ("review.txt", b"review", "text/plain")},
    )

    assert response.status_code == 411


def test_filename_sanitization_handles_absolute_paths_and_reserved_names() -> None:
    assert safe_original_filename("C:\\Users\\Reviewer\\sample.csv") == "sample.csv"
    with pytest.raises(UploadValidationError, match="reserved"):
        safe_original_filename("C:\\temp\\CON.txt")
