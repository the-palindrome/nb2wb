from __future__ import annotations

import base64
import binascii
from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from pathlib import PurePosixPath
from tempfile import NamedTemporaryFile
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class OCRRequest:
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
        raise NotImplementedError

    @contextmanager
    def input_image_path(self, request: OCRRequest):
        path = self.resolve_image_path(request)
        if path is not None:
            yield str(path)
            return

        pil_image = self.load_image(request)
        with NamedTemporaryFile(suffix=".png") as handle:
            pil_image.save(handle.name, format="PNG")
            yield handle.name

    def load_image(self, request: OCRRequest):
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
        resolved = path.expanduser()
        if not resolved.exists():
            raise FileNotFoundError(f"image '{resolved}' not found for OCR")
        with image_module.open(resolved) as handle:
            return handle.convert("RGB")

    def candidate_texts(self, request: OCRRequest) -> list[str]:
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
        return " ".join(self.candidate_texts(request)).lower()

    @staticmethod
    def filename_from_src(src: str) -> str:
        if not src:
            return ""
        parsed = urlparse(src)
        path = parsed.path or src
        return unquote(PurePosixPath(path).name)

    @staticmethod
    def _load_data_uri_image(src: str, image_module):
        header, _, payload = src.partition(",")
        if not header or not payload or ";base64" not in header.lower():
            raise ValueError("unsupported data URI image source")
        try:
            data = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("invalid base64 image payload") from exc
        with image_module.open(BytesIO(data)) as handle:
            return handle.convert("RGB")


__all__ = [
    "BaseOCRPipeline",
    "OCRRequest",
]
