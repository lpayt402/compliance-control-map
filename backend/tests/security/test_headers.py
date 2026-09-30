def test_security_headers_are_present(requirements_client) -> None:
    response = requirements_client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_global_request_body_limit_rejects_declared_oversize_body(requirements_client) -> None:
    maximum = requirements_client.app.state.settings.max_upload_bytes + 256 * 1024
    response = requirements_client.post(
        "/api/v1/auth/login",
        content=b"{}",
        headers={"Content-Length": str(maximum + 1)},
    )

    assert response.status_code == 413
