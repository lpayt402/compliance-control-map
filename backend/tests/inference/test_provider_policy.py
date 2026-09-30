import socket

import pytest

from app.inference.models import DataPolicy, TLSPolicy
from app.inference.policy import (
    DestinationPolicyError,
    normalize_base_url,
    validate_provider_destination,
)


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("HTTPS://Models.Example.com:443/v1/", "https://models.example.com/v1"),
        ("http://host.docker.internal:11434/v1/", "http://host.docker.internal:11434/v1"),
        ("https://[2001:db8::1]:8443/v1", "https://[2001:db8::1]:8443/v1"),
    ],
)
def test_base_url_normalization_is_exact_and_stable(raw: str, normalized: str) -> None:
    assert normalize_base_url(raw) == normalized


@pytest.mark.parametrize(
    "url",
    [
        "ftp://models.example.com/v1",
        "https://user:pass@models.example.com/v1",
        "https://models.example.com/v1?tenant=a",
        "https://models.example.com/v1#fragment",
        "https://models.example.com/v1/../admin",
    ],
)
def test_base_url_rejects_ambiguous_or_credentialed_destinations(url: str) -> None:
    with pytest.raises(DestinationPolicyError):
        normalize_base_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/v1",
        "http://0.0.0.0/v1",
        "http://224.0.0.1/v1",
        "http://[::]/v1",
        "http://[ff02::1]/v1",
    ],
)
def test_destination_rejects_metadata_unspecified_link_local_and_multicast(url: str) -> None:
    with pytest.raises(DestinationPolicyError):
        validate_provider_destination(
            url,
            allowed_base_urls=[url],
            tls_policy=TLSPolicy.PLAINTEXT_LOCAL_ONLY,
            data_policy=DataPolicy.LOCAL_ONLY,
        )


def test_destination_requires_exact_allowlist_and_consistent_policy() -> None:
    with pytest.raises(DestinationPolicyError, match="allowlisted"):
        validate_provider_destination(
            "https://models.example.com/v1",
            allowed_base_urls=["https://other.example.com/v1"],
            tls_policy=TLSPolicy.REQUIRED,
            data_policy=DataPolicy.EXTERNAL_ALLOWED,
            resolved_addresses=["8.8.8.8"],
        )
    with pytest.raises(DestinationPolicyError, match="Plaintext"):
        validate_provider_destination(
            "http://models.example.com/v1",
            allowed_base_urls=["http://models.example.com/v1"],
            tls_policy=TLSPolicy.PLAINTEXT_LOCAL_ONLY,
            data_policy=DataPolicy.EXTERNAL_ALLOWED,
            resolved_addresses=["8.8.8.8"],
        )
    with pytest.raises(DestinationPolicyError, match="LOCAL_ONLY"):
        validate_provider_destination(
            "http://10.10.0.5:11434/v1",
            allowed_base_urls=["http://10.10.0.5:11434/v1"],
            tls_policy=TLSPolicy.PLAINTEXT_LOCAL_ONLY,
            data_policy=DataPolicy.EXTERNAL_ALLOWED,
        )


def test_destination_revalidates_dns_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(DestinationPolicyError, match="unsafe"):
        validate_provider_destination(
            "https://models.example.com/v1",
            allowed_base_urls=["https://models.example.com/v1"],
            tls_policy=TLSPolicy.REQUIRED,
            data_policy=DataPolicy.EXTERNAL_ALLOWED,
            resolve=True,
        )


def test_explicit_local_and_https_destinations_are_allowed() -> None:
    assert validate_provider_destination(
        "http://host.docker.internal:11434/v1",
        allowed_base_urls=["http://HOST.docker.internal:11434/v1/"],
        tls_policy=TLSPolicy.PLAINTEXT_LOCAL_ONLY,
        data_policy=DataPolicy.LOCAL_ONLY,
        resolved_addresses=["192.168.65.2"],
    ) == "http://host.docker.internal:11434/v1"
    assert validate_provider_destination(
        "https://models.example.com/v1",
        allowed_base_urls=["https://models.example.com/v1"],
        tls_policy=TLSPolicy.REQUIRED,
        data_policy=DataPolicy.REDACTED_EXTERNAL,
        resolved_addresses=["8.8.8.8"],
    ) == "https://models.example.com/v1"
