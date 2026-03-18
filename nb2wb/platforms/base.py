"""
Abstract base class for platform-specific HTML builders.
"""

from __future__ import annotations

import base64
import mimetypes
import re
import warnings
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

from .._remote_image import (
    ALLOWED_IMAGE_MIME_TYPES as _ALLOWED_IMAGE_MIMES,
    MAX_REMOTE_IMAGE_BYTES as _MAX_IMAGE_BYTES,
    REMOTE_IMAGE_TIMEOUT as _URL_TIMEOUT,
    extract_peer_ip as _extract_peer_ip,
    is_private_host as _is_private_host,
    validate_public_http_url as _shared_validate_public_http_url,
)

# Mapping from data-URI MIME type to file extension
MIME_TO_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
}

_IMG_TAG_RE = re.compile(
    r'<img\s+[^>]*src="([^"]+)"[^>]*/?>',
    re.IGNORECASE,
)

_ALT_ATTR_RE = re.compile(r'alt="([^"]*)"')


def _rewrite_img_tags(
    html: str,
    rewrite: Callable[[str, str], str],
) -> str:
    """Rewrite ``<img>`` tags using a callback for each source value.

    Args:
        html: HTML string whose image tags should be rewritten.
        rewrite: Callback receiving the full tag HTML and current ``src``.

    Returns:
        HTML with matched image tags replaced by callback output.
    """

    def _sub(match: re.Match[str]) -> str:
        """Delegate an image-tag match to the active rewrite callback.

        Args:
            match: Regex match containing the full image tag and its source.

        Returns:
            Replacement HTML for the matched image tag.
        """
        return rewrite(match.group(0), match.group(1))

    return _IMG_TAG_RE.sub(_sub, html)


def _validate_public_http_url(url: str, *, context: str = "Image URL") -> str:
    """Validate that a URL is public HTTP(S) and safe to fetch."""
    return _shared_validate_public_http_url(
        url,
        context=context,
        is_private_host_fn=_is_private_host,
    )


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that rejects redirects to non-public hosts."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_public_http_url(newurl, context="Redirect target")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PlatformBuilder(ABC):
    """
    Base class for platform-specific HTML builders.

    Each platform has different requirements for HTML structure, CSS styling,
    and interactive features. Subclasses implement platform-specific rendering.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the human-readable platform name.

        Args:
            None.

        Returns:
            Display name for the platform builder.
        """
        pass

    @abstractmethod
    def build_page(self, content_html: str, *, raw_mode: bool = False) -> str:
        """
        Wrap converted cell content in a complete HTML page.

        Args:
            content_html: HTML fragments from converted notebook cells
            raw_mode: When True, omit preview-only toolbar chrome.

        Returns:
            Complete HTML document ready for the platform
        """
        pass

    # ---- shared safe image helpers ----------------------------------------

    @staticmethod
    def _rewrite_image_sources(
        html: str,
        rewrite_src: Callable[[str], str],
    ) -> str:
        """Rewrite image ``src`` values while preserving other attributes.

        Args:
            html: HTML string whose image sources should be rewritten.
            rewrite_src: Callback that rewrites a single image source string.

        Returns:
            HTML with image sources rewritten by the callback.
        """

        def rewrite_image(full_tag: str, img_src: str) -> str:
            """Rewrite one image tag while preserving non-``src`` attributes.

            Args:
                full_tag: Original HTML for the matched image tag.
                img_src: Current ``src`` value extracted from the tag.

            Returns:
                Updated image HTML, or an empty string to drop the tag.
            """
            new_src = rewrite_src(img_src)
            if not new_src:
                return ""
            if new_src == img_src:
                return full_tag
            return full_tag.replace(f'src="{img_src}"', f'src="{new_src}"', 1)

        return _rewrite_img_tags(html, rewrite_image)

    def _to_data_uri(self, src: str) -> str:
        """Convert an image URL or file path to a base64 data URI.

        Applies safety checks:
        - URLs: blocks private/loopback hosts (SSRF), enforces timeout and
          size limit, validates MIME type.
        - File paths: rejects absolute paths and ``..`` traversal.

        Args:
            src: Image URL or relative file path to convert.

        Returns:
            A base64 image data URI, or an empty string on failure.
        """
        try:
            if src.startswith(("http://", "https://")):
                return self._fetch_url_as_data_uri(src)
            return self._read_file_as_data_uri(src)
        except Exception as exc:
            warnings.warn(
                f"Could not convert image '{src}' to data URI: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            return ""

    def _embed_images_as_data_uris(self, html: str) -> str:
        """Convert non-data-URI image sources in HTML into data URIs.

        Args:
            html: HTML string whose image sources should be embedded.

        Returns:
            HTML with eligible image sources converted to data URIs.
        """
        return self._rewrite_image_sources(
            html,
            lambda src: src if src.startswith("data:") else self._to_data_uri(src),
        )

    @staticmethod
    def _fetch_url_as_data_uri(url: str) -> str:
        """Fetch a remote image with SSRF, timeout, size, and MIME checks.

        Args:
            url: Remote HTTP or HTTPS image URL to fetch.

        Returns:
            A base64 image data URI for the fetched image.
        """
        _validate_public_http_url(url)

        opener = urllib.request.build_opener(_SafeRedirectHandler())
        req = urllib.request.Request(url)
        with opener.open(req, timeout=_URL_TIMEOUT) as response:
            _validate_public_http_url(response.geturl(), context="Final response URL")
            peer_ip = _extract_peer_ip(response)
            if peer_ip and _is_private_host(peer_ip):
                raise ValueError(
                    f"Refusing response from private/loopback peer IP: {peer_ip}"
                )

            # Check Content-Length header first (if provided)
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    declared_size = int(content_length)
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid Content-Length header for {url}: {content_length!r}"
                    ) from exc
                if declared_size > _MAX_IMAGE_BYTES:
                    raise ValueError(
                        f"Image too large ({declared_size} bytes, "
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
                    raise ValueError(f"Image exceeds {_MAX_IMAGE_BYTES} byte limit")
                chunks.append(chunk)
            image_data = b"".join(chunks)

            mime_type = response.headers.get_content_type()

        if mime_type not in _ALLOWED_IMAGE_MIMES:
            raise ValueError(f"Disallowed MIME type '{mime_type}' for image at {url}")

        b64_data = base64.b64encode(image_data).decode("utf-8")
        return f"data:{mime_type};base64,{b64_data}"

    @staticmethod
    def _read_file_as_data_uri(src: str) -> str:
        """Read a local image file with path-traversal protection.

        Args:
            src: Relative image path to read from the working directory.

        Returns:
            A base64 image data URI for the file contents.
        """
        raw = Path(src)

        if raw.is_absolute():
            raise ValueError(f"Absolute image path not allowed: {src}")
        if ".." in raw.parts:
            raise ValueError(f"Path traversal ('..') not allowed in image path: {src}")

        cwd = Path.cwd().resolve()
        file_path = (cwd / raw).resolve(strict=True)
        if not file_path.is_relative_to(cwd):
            raise ValueError(
                f"Resolved image path escapes current working directory: {src}"
            )
        if not file_path.is_file():
            raise ValueError(f"Image path is not a file: {src}")

        with open(file_path, "rb") as f:
            image_data = f.read(_MAX_IMAGE_BYTES + 1)
        if len(image_data) > _MAX_IMAGE_BYTES:
            raise ValueError(f"Image file exceeds {_MAX_IMAGE_BYTES} byte limit: {src}")

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "image/png"
        if mime_type not in _ALLOWED_IMAGE_MIMES:
            raise ValueError(f"Disallowed MIME type '{mime_type}' for file: {src}")

        b64_data = base64.b64encode(image_data).decode("utf-8")
        return f"data:{mime_type};base64,{b64_data}"

    def _make_images_copyable(self, html: str) -> str:
        """Wrap each ``<img>`` in a container with an inline copy button.

        Args:
            html: HTML string whose images should become copyable.

        Returns:
            HTML with image tags replaced by copy-button wrappers.
        """

        def wrap_image(full_tag: str, img_src: str) -> str:
            """Wrap one image tag in copy-button markup.

            Args:
                full_tag: Original HTML for the matched image tag.
                img_src: Current ``src`` value extracted from the tag.

            Returns:
                Replacement HTML containing the wrapped copyable image.
            """

            if not img_src.startswith("data:"):
                img_src = self._to_data_uri(img_src)
            if not img_src:
                return ""

            alt_match = _ALT_ATTR_RE.search(full_tag)
            alt_text = alt_match.group(1) if alt_match else "image"

            return (
                f'<div class="image-container">'
                f'<img src="{img_src}" alt="{alt_text}">'
                f'<button class="copy-image-btn" type="button">Copy image</button>'
                f"</div>"
            )

        return _rewrite_img_tags(html, wrap_image)
