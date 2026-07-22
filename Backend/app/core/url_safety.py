from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Iterable
from urllib.parse import urlparse

from app.exceptions import ValidationError


AddressResolver = Callable[[str, int], Awaitable[Iterable[str]]]

_BLOCKED_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata.aws.internal",
}
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal")


async def _resolve_addresses(hostname: str, port: int) -> list[str]:
    def resolve() -> list[str]:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        return list(dict.fromkeys(str(info[4][0]) for info in infos))

    try:
        return await asyncio.to_thread(resolve)
    except socket.gaierror as exc:
        raise ValidationError("URL host could not be resolved") from exc


def _is_public_address(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


async def validate_public_http_url(
    raw_url: str,
    *,
    resolver: AddressResolver | None = None,
) -> str:
    """Reject URLs that could make the backend reach private or metadata services."""
    value = str(raw_url or "").strip()
    if not value:
        raise ValidationError("URL is required")
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError as exc:
        raise ValidationError("URL is malformed") from exc
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValidationError("Only http and https URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise ValidationError("URL credentials are not allowed")
    hostname = str(parsed.hostname or "").rstrip(".").casefold()
    if not hostname:
        raise ValidationError("URL hostname is required")
    if hostname in _BLOCKED_HOSTS or hostname.endswith(_BLOCKED_SUFFIXES):
        raise ValidationError("Private or local URL hosts are not allowed")
    if port not in {None, 80, 443}:
        raise ValidationError("Only standard HTTP/HTTPS ports are allowed")

    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    addresses = (
        [str(literal)]
        if literal is not None
        else list(await (resolver or _resolve_addresses)(hostname, port or (443 if parsed.scheme.lower() == "https" else 80)))
    )
    if not addresses or any(not _is_public_address(address) for address in addresses):
        raise ValidationError("Private, local, reserved or unresolved URL targets are not allowed")
    return value


__all__ = ["AddressResolver", "validate_public_http_url"]
