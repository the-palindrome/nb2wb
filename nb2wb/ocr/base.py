from __future__ import annotations

import base64
import binascii
from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
import mimetypes
from pathlib import Path
from pathlib import PurePosixPath
from tempfile import NamedTemporaryFile
from urllib.parse import unquote, urlparse


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
    """Base class for OCR pipelines that need shared image-loading helpers."""

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
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover - Pillow is a core dependency.
            raise RuntimeError("Pillow is required to load images for OCR.") from exc

        src = request.src.strip()
        if not src:
            raise ValueError("image source is empty")

        if src.startswith("data:"):
            return self._load_data_uri_image(src, Image)

        path = self.resolve_image_path(request)
        if path is None:
            raise ValueError("remote image URLs are not supported for OCR")
        return self.open_pil_image(path, Image)

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

        path = self.resolve_image_path(request)
        if path is None:
            raise ValueError("remote image URLs are not supported for OCR")

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


__all__ = [
    "BaseOCRPipeline",
    "OCRRequest",
]
