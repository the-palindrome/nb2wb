from __future__ import annotations

import base64
import binascii
from contextlib import contextmanager
from dataclasses import dataclass
import ipaddress
from io import BytesIO
import mimetypes
from pathlib import Path
from pathlib import PurePosixPath
import socket
from tempfile import NamedTemporaryFile
from time import monotonic
import urllib.request
from urllib.parse import unquote, urlparse

_MAX_REMOTE_IMAGE_BYTES = 50 * 1024 * 1024
_REMOTE_IMAGE_TIMEOUT = 30
_ALLOWED_REMOTE_IMAGE_MIME_TYPES = frozenset(
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


@dataclass(frozen=True)
class OCRRequest:
    """Describe one image OCR request and its nearby context.

    Attributes:
        src: Image source URL, path, or data URI.
        alt: Image alt text from the source document.
        title: Image title attribute from the source document.
        classes: CSS classes associated with the image or wrapper.
        caption: Visible caption text near the image.
        nearby_text: Other text surrounding the image.
        source_dir: Base directory for resolving relative image paths.
    """

    src: str
    alt: str = ""
    title: str = ""
    classes: tuple[str, ...] = ()
    caption: str = ""
    nearby_text: str = ""
    source_dir: Path | None = None


class BaseOCRPipeline:
    """Base class for OCR pipelines that need shared image-loading helpers.

    Subclasses should prefer ``load_image()``, ``read_image_bytes()``, and
    ``input_image_path()`` so they automatically support local paths, data URIs,
    and SSRF-safe public HTTP(S) image URLs.
    """

    def __call__(self, request: OCRRequest) -> dict[str, str]:
        """Run OCR for one image request.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A result mapping containing ``type`` and ``payload`` keys.
        """
        raise NotImplementedError

    @contextmanager
    def input_image_path(self, request: OCRRequest):
        """Yield a filesystem path for OCR engines that require path input.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A context-managed path string pointing to the source image.
        """
        path = self.resolve_image_path(request)
        if path is not None:
            yield str(path)
            return

        pil_image = self.load_image(request)
        with NamedTemporaryFile(suffix=".png") as handle:
            pil_image.save(handle.name, format="PNG")
            yield handle.name

    def load_image(self, request: OCRRequest):
        """Load the request image into a Pillow RGB image.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A Pillow image converted to RGB mode.
        """
        image_module = self._image_module()

        src = request.src.strip()
        if not src:
            raise ValueError("image source is empty")

        if src.startswith("data:"):
            return self._load_data_uri_image(src, image_module)

        if self._is_remote_http_source(src):
            image_data, _mime_type = self._fetch_remote_image_bytes(src)
            return self._load_image_bytes(image_data, image_module)

        path = self.resolve_image_path(request)
        if path is None:
            raise ValueError("unsupported image source for OCR")
        return self.open_pil_image(path, image_module)

    def resolve_image_path(self, request: OCRRequest) -> Path | None:
        """Resolve a local filesystem path for an image source when possible.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A resolved local ``Path`` or ``None`` for remote/data URI images.
        """
        src = request.src.strip()
        if not src or src.startswith("data:"):
            return None

        parsed = urlparse(src)
        if parsed.scheme in {"http", "https"}:
            return None
        if parsed.scheme == "file":
            return Path(unquote(parsed.path))

        path = Path(unquote(parsed.path or src))
        if not path.is_absolute() and request.source_dir is not None:
            path = request.source_dir / path
        return path

    def open_pil_image(self, path: Path, image_module):
        """Open an image from disk and normalize it to RGB mode.

        Args:
            path: Filesystem path to the source image.
            image_module: Pillow image module used to open the file.

        Returns:
            A Pillow image converted to RGB mode.
        """
        resolved = path.expanduser()
        if not resolved.exists():
            raise FileNotFoundError(f"image '{resolved}' not found for OCR")
        with image_module.open(resolved) as handle:
            return handle.convert("RGB")

    def read_image_bytes(self, request: OCRRequest) -> tuple[bytes, str]:
        """Read the source image as raw bytes and detect its MIME type.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A ``(bytes, mime_type)`` tuple for the image.
        """
        src = request.src.strip()
        if not src:
            raise ValueError("image source is empty")

        if src.startswith("data:"):
            return self._decode_data_uri(src)

        if self._is_remote_http_source(src):
            return self._fetch_remote_image_bytes(src)

        path = self.resolve_image_path(request)
        if path is None:
            raise ValueError("unsupported image source for OCR")

        resolved = path.expanduser()
        if not resolved.exists():
            raise FileNotFoundError(f"image '{resolved}' not found for OCR")

        mime_type = self._guess_image_mime_type(resolved)
        if mime_type is not None:
            return resolved.read_bytes(), mime_type

        image = self.load_image(request)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue(), "image/png"

    def _fetch_remote_image_bytes(self, src: str) -> tuple[bytes, str]:
        """Fetch a remote HTTP(S) image with SSRF, timeout, and size checks.

        Args:
            src: Remote image URL to fetch.

        Returns:
            A ``(bytes, mime_type)`` tuple for the fetched image.
        """
        _validate_public_http_url(src)

        deadline = monotonic() + _REMOTE_IMAGE_TIMEOUT
        opener = urllib.request.build_opener(_SafeRedirectHandler())
        request = urllib.request.Request(src)
        with opener.open(request, timeout=max(0.0, deadline - monotonic())) as response:
            final_url = response.geturl()
            _validate_public_http_url(final_url, context="Final response URL")
            peer_ip = _extract_peer_ip(response)
            if peer_ip and _is_private_host(peer_ip):
                raise ValueError(
                    f"Refusing response from private/loopback peer IP: {peer_ip}"
                )

            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    declared_size = int(content_length)
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid Content-Length header for {src}: {content_length!r}"
                    ) from exc
                if declared_size > _MAX_REMOTE_IMAGE_BYTES:
                    raise ValueError(
                        f"Image too large ({declared_size} bytes, "
                        f"max {_MAX_REMOTE_IMAGE_BYTES})"
                    )

            chunks: list[bytes] = []
            total = 0
            while True:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"Timed out fetching image from {src}")
                raw = getattr(getattr(response, "fp", None), "raw", None)
                sock = getattr(raw, "_sock", None) if raw is not None else None
                if sock is None:
                    sock = getattr(getattr(response, "fp", None), "_sock", None)
                if sock is not None:
                    sock.settimeout(remaining)
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_REMOTE_IMAGE_BYTES:
                    raise ValueError(
                        f"Image exceeds {_MAX_REMOTE_IMAGE_BYTES} byte limit"
                    )
                chunks.append(chunk)
            image_data = b"".join(chunks)
            mime_type = response.headers.get_content_type()

        if mime_type in _ALLOWED_REMOTE_IMAGE_MIME_TYPES:
            return image_data, mime_type

        # Some servers mislabel images (for example as application/octet-stream).
        # Fall back to decoding with Pillow and re-encoding to PNG.
        try:
            image = self._load_image_bytes(image_data, self._image_module())
        except Exception as exc:
            raise ValueError(
                f"Disallowed MIME type '{mime_type}' for image at {src}"
            ) from exc
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue(), "image/png"

    def image_data_url(self, request: OCRRequest) -> str:
        """Encode the source image as a base64 data URL.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A ``data:...;base64,...`` URL containing the image bytes.
        """
        data, mime_type = self.read_image_bytes(request)
        payload = base64.b64encode(data).decode("ascii")
        return f"data:{mime_type};base64,{payload}"

    def candidate_texts(self, request: OCRRequest) -> list[str]:
        """Collect textual hints that may help classify an image.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A list of non-empty text fragments related to the image.
        """
        filename = self.filename_from_src(request.src)
        parts = [
            request.alt,
            request.title,
            request.caption,
            request.nearby_text,
            " ".join(request.classes),
            filename,
        ]
        return [part for part in parts if part]

    def classification_haystack(self, request: OCRRequest) -> str:
        """Collapse image context strings into one lowercase search blob.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A lowercase string combining all candidate text fragments.
        """
        return " ".join(self.candidate_texts(request)).lower()

    @staticmethod
    def filename_from_src(src: str) -> str:
        """Extract a filename hint from an image source value.

        Args:
            src: Image source URL, path, or data URI.

        Returns:
            The final path segment, or an empty string when unavailable.
        """
        if not src:
            return ""
        parsed = urlparse(src)
        path = parsed.path or src
        return unquote(PurePosixPath(path).name)

    @staticmethod
    def _load_data_uri_image(src: str, image_module):
        """Decode a data URI image and open it with Pillow.

        Args:
            src: Base64 image data URI.
            image_module: Pillow image module used to open the payload.

        Returns:
            A Pillow image converted to RGB mode.
        """
        data, _mime_type = BaseOCRPipeline._decode_data_uri(src)
        return BaseOCRPipeline._load_image_bytes(data, image_module)

    @staticmethod
    def _load_image_bytes(data: bytes, image_module):
        """Decode raw image bytes and normalize to RGB mode.

        Args:
            data: Raw image bytes.
            image_module: Pillow image module used to open the payload.

        Returns:
            A Pillow image converted to RGB mode.
        """
        with image_module.open(BytesIO(data)) as handle:
            return handle.convert("RGB")

    @staticmethod
    def _decode_data_uri(src: str) -> tuple[bytes, str]:
        """Decode a base64-encoded image data URI.

        Args:
            src: Data URI containing an image payload.

        Returns:
            A ``(bytes, mime_type)`` tuple extracted from the data URI.
        """
        header, _, payload = src.partition(",")
        if not header or not payload or ";base64" not in header.lower():
            raise ValueError("unsupported data URI image source")
        mime_type = header[5:].split(";", 1)[0].strip() or "application/octet-stream"
        try:
            data = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("invalid base64 image payload") from exc
        return data, mime_type

    @staticmethod
    def _guess_image_mime_type(path: Path) -> str | None:
        """Guess an image MIME type from a filesystem path.

        Args:
            path: Image path whose suffix should be inspected.

        Returns:
            An ``image/*`` MIME type string, or ``None`` when unknown.
        """
        mime_type, _encoding = mimetypes.guess_type(path.name)
        if mime_type and mime_type.startswith("image/"):
            return mime_type
        return None

    @staticmethod
    def _is_remote_http_source(src: str) -> bool:
        """Check whether a source string is an HTTP(S) URL."""
        parsed = urlparse(src)
        return parsed.scheme in {"http", "https"}

    @staticmethod
    def _image_module():
        """Import and return the Pillow ``Image`` module."""
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover - Pillow is a core dependency.
            raise RuntimeError("Pillow is required to load images for OCR.") from exc
        return Image


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that rejects redirects to non-public hosts."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Validate redirect targets before following them."""
        _validate_public_http_url(newurl, context="Redirect target")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _validate_public_http_url(url: str, *, context: str = "Image URL") -> str:
    """Validate that a URL is public HTTP(S) and safe to fetch."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"{context} must use http/https: {url}")
    if parsed.username or parsed.password:
        raise ValueError(f"{context} must not contain credentials: {url}")

    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError(f"{context} is missing a hostname: {url}")

    if _is_private_host(hostname):
        raise ValueError(
            f"Refusing to fetch image from private/loopback host: {hostname}"
        )

    return hostname


def _is_private_host(hostname: str) -> bool:
    """Check whether a hostname resolves to a non-public address."""

    def _is_non_public(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
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
        addr = ipaddress.ip_address(hostname)
        return _is_non_public(addr)
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        if not infos:
            return True
        for _family, _type, _proto, _canonname, sockaddr in infos:
            addr = ipaddress.ip_address(sockaddr[0])
            if _is_non_public(addr):
                return True
    except OSError:
        return True
    return False


def _extract_peer_ip(response) -> str | None:
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


__all__ = [
    "BaseOCRPipeline",
    "OCRRequest",
]
