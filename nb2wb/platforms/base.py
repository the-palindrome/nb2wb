"""
Abstract base class for platform-specific HTML builders.
"""
from __future__ import annotations

import base64
import ipaddress
import mimetypes
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urlparse

# Maximum image download size: 50 MB
_MAX_IMAGE_BYTES = 50 * 1024 * 1024

# URL fetch timeout in seconds
_URL_TIMEOUT = 30

# Allowed image MIME types
_ALLOWED_IMAGE_MIMES = frozenset({
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/svg+xml",
    "image/webp",
    "image/bmp",
    "image/tiff",
})


def _is_private_host(hostname: str) -> bool:
    """Return True if *hostname* resolves to a private/loopback address."""
    try:
        addr = ipaddress.ip_address(hostname)
        return addr.is_private or addr.is_loopback or addr.is_reserved
    except ValueError:
        pass
    # Hostname like "localhost" — resolve it
    import socket
    try:
        infos = socket.getaddrinfo(hostname, None)
        for _family, _type, _proto, _canonname, sockaddr in infos:
            addr = ipaddress.ip_address(sockaddr[0])
            if addr.is_private or addr.is_loopback or addr.is_reserved:
                return True
    except socket.gaierror:
        pass
    return False


class PlatformBuilder(ABC):
    """
    Base class for platform-specific HTML builders.

    Each platform has different requirements for HTML structure, CSS styling,
    and interactive features. Subclasses implement platform-specific rendering.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable platform name."""
        pass

    @abstractmethod
    def build_page(self, content_html: str) -> str:
        """
        Wrap converted cell content in a complete HTML page.

        Args:
            content_html: HTML fragments from converted notebook cells

        Returns:
            Complete HTML document ready for the platform
        """
        pass

    # ---- shared safe image helpers ----------------------------------------

    def _to_data_uri(self, src: str) -> str:
        """Convert an image URL or file path to a base64 data URI.

        Applies safety checks:
        - URLs: blocks private/loopback hosts (SSRF), enforces timeout and
          size limit, validates MIME type.
        - File paths: rejects absolute paths and ``..`` traversal.
        """
        try:
            if src.startswith(("http://", "https://")):
                return self._fetch_url_as_data_uri(src)
            return self._read_file_as_data_uri(src)
        except Exception as e:
            print(f"Warning: Could not convert image '{src}' to data URI: {e}")
            return src

    @staticmethod
    def _fetch_url_as_data_uri(url: str) -> str:
        """Fetch a remote image with SSRF, timeout, size, and MIME checks."""
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        if _is_private_host(hostname):
            raise ValueError(
                f"Refusing to fetch image from private/loopback host: {hostname}"
            )

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=_URL_TIMEOUT) as response:
            # Check Content-Length header first (if provided)
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > _MAX_IMAGE_BYTES:
                raise ValueError(
                    f"Image too large ({int(content_length)} bytes, "
                    f"max {_MAX_IMAGE_BYTES})"
                )

            # Read in chunks up to the limit
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_IMAGE_BYTES:
                    raise ValueError(
                        f"Image exceeds {_MAX_IMAGE_BYTES} byte limit"
                    )
                chunks.append(chunk)
            image_data = b"".join(chunks)

            mime_type = response.headers.get_content_type()

        if mime_type not in _ALLOWED_IMAGE_MIMES:
            raise ValueError(
                f"Disallowed MIME type '{mime_type}' for image at {url}"
            )

        b64_data = base64.b64encode(image_data).decode("utf-8")
        return f"data:{mime_type};base64,{b64_data}"

    @staticmethod
    def _read_file_as_data_uri(src: str) -> str:
        """Read a local image file with path-traversal protection."""
        raw = Path(src)

        if raw.is_absolute():
            raise ValueError(
                f"Absolute image path not allowed: {src}"
            )
        if ".." in raw.parts:
            raise ValueError(
                f"Path traversal ('..') not allowed in image path: {src}"
            )

        file_path = Path.cwd() / raw

        with open(file_path, "rb") as f:
            image_data = f.read(_MAX_IMAGE_BYTES + 1)
        if len(image_data) > _MAX_IMAGE_BYTES:
            raise ValueError(
                f"Image file exceeds {_MAX_IMAGE_BYTES} byte limit: {src}"
            )

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "image/png"
        if mime_type not in _ALLOWED_IMAGE_MIMES:
            raise ValueError(
                f"Disallowed MIME type '{mime_type}' for file: {src}"
            )

        b64_data = base64.b64encode(image_data).decode("utf-8")
        return f"data:{mime_type};base64,{b64_data}"
