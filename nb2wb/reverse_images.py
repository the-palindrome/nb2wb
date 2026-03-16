from __future__ import annotations

import base64
import binascii
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from pathlib import PurePosixPath
import re
from tempfile import NamedTemporaryFile
from typing import Literal
from urllib.parse import unquote, urlparse

ImageClassification = Literal["code", "latex", "table", "other"]
OCR_DEVICE_CHOICES = frozenset({"cpu", "cuda", "gpu", "mps"})

SUPPORTED_LANGUAGE_ALIASES: dict[str, str] = {
    "python": "python",
    "py": "python",
    "r": "r",
    "julia": "julia",
    "jl": "julia",
    "bash": "bash",
    "sh": "bash",
    "shell": "bash",
    "zsh": "bash",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "sql": "sql",
}

_LANGUAGE_HINT_RE = re.compile(r"\b([a-z][a-z0-9+-]{0,30})\b")
_LATEX_HINTS = ("math", "latex", "equation", "formula")
_CODE_HINTS = ("code", "snippet", "source", "terminal")
_TABLE_HINTS = ("table", "tabular", "dataframe", "grid")


@dataclass(frozen=True)
class ImageCandidate:
    src: str
    alt: str = ""
    title: str = ""
    classes: tuple[str, ...] = ()
    caption: str = ""
    nearby_text: str = ""
    source_dir: Path | None = None


class DefaultImageClassifier:
    """Classify images using HTML metadata only."""

    def classify(self, image: ImageCandidate) -> ImageClassification:
        haystack = _classification_haystack(image)
        if any(hint in haystack for hint in _LATEX_HINTS):
            return "latex"
        if any(hint in haystack for hint in _CODE_HINTS):
            return "code"
        if any(hint in haystack for hint in _TABLE_HINTS):
            return "table"
        if infer_supported_language(image) is not None:
            return "code"
        return "other"


def infer_supported_language(image: ImageCandidate) -> str | None:
    """Infer a scaffold-supported language from image metadata."""
    for text in _candidate_texts(image):
        normalized = normalize_supported_language(text)
        if normalized is not None:
            return normalized

        for match in _LANGUAGE_HINT_RE.finditer(text.lower()):
            normalized = normalize_supported_language(match.group(1))
            if normalized is not None:
                return normalized
    return None


def normalize_supported_language(raw: str | None) -> str | None:
    if not raw:
        return None

    cleaned = raw.strip().lower().lstrip(".")
    if cleaned in SUPPORTED_LANGUAGE_ALIASES:
        return SUPPORTED_LANGUAGE_ALIASES[cleaned]

    for token in re.split(r"[^a-z0-9+-]+", cleaned):
        if token in SUPPORTED_LANGUAGE_ALIASES:
            return SUPPORTED_LANGUAGE_ALIASES[token]
    return None


def normalize_ocr_device(device: str | None) -> str | None:
    if device is None:
        return None
    normalized = device.strip().lower()
    if not normalized or normalized == "auto":
        return None
    if normalized not in OCR_DEVICE_CHOICES:
        allowed = ", ".join(sorted((*OCR_DEVICE_CHOICES, "auto")))
        raise ValueError(f"device must be one of: {allowed}")
    return normalized


def extract_latex(image: ImageCandidate, *, device: str | None = None) -> str:
    """Run Pix2Text OCR for a LaTeX-classified image."""
    model = _load_latex_ocr_model(normalize_ocr_device(device))
    with _pix2text_input_path(image) as image_path:
        result = _run_latex_ocr(model, image_path)
    if not result:
        raise RuntimeError("Pix2Text returned empty LaTeX output")
    return result


@lru_cache(maxsize=8)
def _load_latex_ocr_model(device: str | None = None):
    try:
        from pix2text.latex_ocr import LatexOCR
    except ImportError as exc:  # pragma: no cover - depends on optional dependency.
        raise RuntimeError(
            "Pix2Text is not installed. Install it with `pip install nb2wb[ocr]` "
            "or `pip install pix2text` to enable LaTeX OCR."
        ) from exc
    return LatexOCR(**_latex_ocr_model_config(device))


@contextmanager
def _pix2text_input_path(image: ImageCandidate):
    path = _resolve_image_path(image)
    if path is not None:
        yield str(path)
        return

    pil_image = _load_image(image)
    with NamedTemporaryFile(suffix=".png") as handle:
        pil_image.save(handle.name, format="PNG")
        yield handle.name


def _load_image(image: ImageCandidate):
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - Pillow is a core dependency.
        raise RuntimeError("Pillow is required to load images for OCR.") from exc

    src = image.src.strip()
    if not src:
        raise ValueError("image source is empty")

    if src.startswith("data:"):
        return _load_data_uri_image(src, Image)

    path = _resolve_image_path(image)
    if path is None:
        raise ValueError("remote image URLs are not supported for LaTeX OCR")
    return _open_pil_image(path, Image)


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


def _open_pil_image(path: Path, image_module):
    resolved = path.expanduser()
    if not resolved.exists():
        raise FileNotFoundError(f"image '{resolved}' not found for LaTeX OCR")
    with image_module.open(resolved) as handle:
        return handle.convert("RGB")


def _resolve_image_path(image: ImageCandidate) -> Path | None:
    src = image.src.strip()
    if not src or src.startswith("data:"):
        return None

    parsed = urlparse(src)
    if parsed.scheme in {"http", "https"}:
        return None
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))

    path = Path(unquote(parsed.path or src))
    if not path.is_absolute() and image.source_dir is not None:
        path = image.source_dir / path
    return path


def _latex_ocr_model_config(device: str | None) -> dict[str, object]:
    model_backend = "pytorch" if device == "mps" else "onnx"
    more_processor_configs: dict[str, object] = {"use_fast": True}
    more_model_configs: dict[str, object] = {"use_cache": False}

    if model_backend == "onnx":
        more_model_configs["encoder_file_name"] = "encoder_model.onnx"
        more_model_configs["decoder_file_name"] = "decoder_model.onnx"
        if device == "cuda":
            more_model_configs["provider"] = "CUDAExecutionProvider"
        elif device == "cpu":
            more_model_configs["provider"] = "CPUExecutionProvider"

    return {
        "model_backend": model_backend,
        "device": device,
        "more_processor_configs": more_processor_configs,
        "more_model_configs": more_model_configs,
    }


def _run_latex_ocr(model, image_path: str) -> str:
    if hasattr(model, "recognize"):
        result = model.recognize(image_path, use_post_process=True)
        return _normalize_latex_ocr_result(result)
    return _normalize_latex_ocr_result(model(image_path))


def _normalize_latex_ocr_result(result) -> str:
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        for key in ("text", "latex", "result"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
    if isinstance(result, list):
        parts = [_normalize_latex_ocr_result(item) for item in result]
        return "\n".join(part for part in parts if part).strip()
    return str(result).strip()


def _classification_haystack(image: ImageCandidate) -> str:
    return " ".join(_candidate_texts(image)).lower()


def _candidate_texts(image: ImageCandidate) -> list[str]:
    filename = _filename_from_src(image.src)
    parts = [
        image.alt,
        image.title,
        image.caption,
        image.nearby_text,
        " ".join(image.classes),
        filename,
    ]
    return [part for part in parts if part]


def _filename_from_src(src: str) -> str:
    if not src:
        return ""
    parsed = urlparse(src)
    path = parsed.path or src
    return unquote(PurePosixPath(path).name)
