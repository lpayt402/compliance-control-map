import ipaddress
import socket
from urllib.parse import unquote, urlsplit, urlunsplit

from app.inference.models import DataPolicy, TLSPolicy

_METADATA_ADDRESSES = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("fd00:ec2::254"),
}
_LOCAL_HOSTNAMES = {"localhost", "host.docker.internal"}
IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class DestinationPolicyError(ValueError):
    """A provider destination violates the server's outbound network policy."""


def normalize_base_url(raw: str) -> str:
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise DestinationPolicyError("Provider base URL is invalid.") from exc
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise DestinationPolicyError("Provider base URL must use HTTP or HTTPS.")
    if parsed.username is not None or parsed.password is not None:
        raise DestinationPolicyError("Provider base URL must not contain credentials.")
    if parsed.query or parsed.fragment:
        raise DestinationPolicyError("Provider base URL must not contain a query or fragment.")
    hostname = parsed.hostname
    if not hostname:
        raise DestinationPolicyError("Provider base URL must contain a hostname.")
    decoded_segments = unquote(parsed.path).split("/")
    if any(segment in {".", ".."} for segment in decoded_segments):
        raise DestinationPolicyError("Provider base URL path must not contain traversal segments.")

    scheme = parsed.scheme.casefold()
    normalized_host = hostname.casefold().encode("idna").decode("ascii")
    try:
        address = ipaddress.ip_address(normalized_host)
    except ValueError:
        rendered_host = normalized_host
    else:
        rendered_host = f"[{address.compressed}]" if address.version == 6 else address.compressed
    default_port = 443 if scheme == "https" else 80
    netloc = rendered_host if port in {None, default_port} else f"{rendered_host}:{port}"
    path = parsed.path.rstrip("/")
    return urlunsplit((scheme, netloc, path, "", ""))


def _addresses(hostname: str, port: int, *, resolve: bool) -> tuple[IPAddress, ...]:
    try:
        return (ipaddress.ip_address(hostname),)
    except ValueError:
        if not resolve:
            return ()
    try:
        answers = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise DestinationPolicyError("Provider hostname could not be resolved.") from exc
    parsed = {ipaddress.ip_address(answer[4][0]) for answer in answers}
    if not parsed:
        raise DestinationPolicyError("Provider hostname returned no addresses.")
    return tuple(sorted(parsed, key=str))


def _is_unsafe(address: IPAddress) -> bool:
    return bool(
        address in _METADATA_ADDRESSES
        or address.is_unspecified
        or address.is_link_local
        or address.is_multicast
    )


def _is_local(address: IPAddress) -> bool:
    return bool(address.is_private or address.is_loopback)


def validate_provider_destination(
    raw: str,
    *,
    allowed_base_urls: list[str],
    tls_policy: TLSPolicy,
    data_policy: DataPolicy,
    resolve: bool = False,
    resolved_addresses: list[str] | None = None,
) -> str:
    normalized = normalize_base_url(raw)
    allowed = {normalize_base_url(item) for item in allowed_base_urls}
    if normalized not in allowed:
        raise DestinationPolicyError("Provider base URL is not exactly allowlisted.")

    parsed = urlsplit(normalized)
    if parsed.scheme == "http" and tls_policy is not TLSPolicy.PLAINTEXT_LOCAL_ONLY:
        raise DestinationPolicyError("Plaintext providers require the local-only TLS policy.")
    if parsed.scheme == "https" and tls_policy is TLSPolicy.PLAINTEXT_LOCAL_ONLY:
        raise DestinationPolicyError("HTTPS providers require a TLS verification policy.")

    hostname = parsed.hostname
    if hostname is None:
        raise DestinationPolicyError("Provider base URL must contain a hostname.")
    if resolved_addresses is None:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = _addresses(hostname, port, resolve=resolve)
    else:
        addresses = tuple(ipaddress.ip_address(item) for item in resolved_addresses)
    if any(_is_unsafe(address) for address in addresses):
        raise DestinationPolicyError("Provider destination resolves to an unsafe address.")

    hostname_local = (
        hostname.casefold() in _LOCAL_HOSTNAMES or hostname.casefold().endswith(".local")
    )
    local = hostname_local or any(_is_local(address) for address in addresses)
    if local and data_policy is not DataPolicy.LOCAL_ONLY:
        raise DestinationPolicyError(
            "Private-network providers must use the LOCAL_ONLY data policy."
        )
    if not local and parsed.scheme == "http":
        raise DestinationPolicyError("Plaintext public provider destinations are not permitted.")
    if not local and data_policy is DataPolicy.LOCAL_ONLY:
        raise DestinationPolicyError("Public provider destinations cannot be marked LOCAL_ONLY.")
    return normalized
