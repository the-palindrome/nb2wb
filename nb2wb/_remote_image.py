from __future__ import annotations

import ipaddress
import socket
import urllib.request
from urllib.parse import urlparse

MAX_REMOTE_IMAGE_BYTES = 50 * 1024 * 1024
REMOTE_IMAGE_TIMEOUT = 30
ALLOWED_IMAGE_MIME_TYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/svg+xml",
        "image/webp",
        "image/bmp",
        "image/tiff",
    }
)


def validate_public_http_url(
    url: str,
    *,
    context: str = "Image URL",
    is_private_host_fn=None,
) -> str:
    """Validate that a URL is public HTTP(S) and safe to fetch."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"{context} must use http/https: {url}")
    if parsed.username or parsed.password:
        raise ValueError(f"{context} must not contain credentials: {url}")

    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError(f"{context} is missing a hostname: {url}")
    if (is_private_host_fn or is_private_host)(hostname):
        raise ValueError(
            f"Refusing to fetch image from private/loopback host: {hostname}"
        )
    return hostname


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that rejects redirects to non-public hosts."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_http_url(newurl, context="Redirect target")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def is_private_host(hostname: str) -> bool:
    """Check whether a hostname resolves to a non-public address."""

    def is_non_public(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        return (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_multicast
            or addr.is_reserved
            or addr.is_unspecified
            or not addr.is_global
        )

    try:
        return is_non_public(ipaddress.ip_address(hostname))
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        if not infos:
            return True
        for _family, _type, _proto, _canonname, sockaddr in infos:
            if is_non_public(ipaddress.ip_address(sockaddr[0])):
                return True
    except OSError:
        return True
    return False


def extract_peer_ip(response) -> str | None:
    """Extract the peer IP address from a urllib response when possible."""
    fp = getattr(response, "fp", None)
    if fp is None:
        return None

    sockets = []
    raw = getattr(fp, "raw", None)
    if raw is not None:
        sock = getattr(raw, "_sock", None)
        if sock is not None:
            sockets.append(sock)
        conn = getattr(raw, "_connection", None)
        if conn is not None:
            conn_sock = getattr(conn, "sock", None)
            if conn_sock is not None:
                sockets.append(conn_sock)
    fp_sock = getattr(fp, "_sock", None)
    if fp_sock is not None:
        sockets.append(fp_sock)

    for sock in sockets:
        try:
            peer = sock.getpeername()
        except OSError:
            continue
        if isinstance(peer, tuple) and peer:
            return str(peer[0])
    return None
