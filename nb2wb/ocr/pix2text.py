from __future__ import annotations

import base64
import binascii
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class OCRRequest:
    src: str
    alt: str = ""
    classification: str = "figure"
    source_dir: Path | None = None


def pix2text_ocr_pipeline(request: OCRRequest) -> dict[str, str]:
    """Default OCR pipeline backed by Pix2Text for LaTeX-oriented images."""
    if request.classification != "latex":
        return {"type": "figure", "payload": ""}

    try:
        model = _load_latex_ocr_model()
        with _pix2text_input_path(request) as image_path:
            result = _run_latex_ocr(model, image_path)
    except Exception:
        return {"type": "figure", "payload": ""}

    if not result:
        return {"type": "figure", "payload": ""}
    return {"type": "latex", "payload": result}


@lru_cache(maxsize=1)
def _load_latex_ocr_model():
    try:
        from pix2text.latex_ocr import LatexOCR
    except ImportError as exc:  # pragma: no cover - depends on optional dependency.
        raise RuntimeError(
            "Pix2Text is not installed. Install it with `pip install nb2wb[ocr]` "
            "or `pip install pix2text` to enable LaTeX OCR."
        ) from exc
    return LatexOCR(**_latex_ocr_model_config())


@contextmanager
def _pix2text_input_path(request: OCRRequest):
    path = _resolve_image_path(request)
    if path is not None:
        yield str(path)
        return

    pil_image = _load_image(request)
    with NamedTemporaryFile(suffix=".png") as handle:
        pil_image.save(handle.name, format="PNG")
        yield handle.name


def _load_image(request: OCRRequest):
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - Pillow is a core dependency.
        raise RuntimeError("Pillow is required to load images for OCR.") from exc

    src = request.src.strip()
    if not src:
        raise ValueError("image source is empty")

    if src.startswith("data:"):
        return _load_data_uri_image(src, Image)

    path = _resolve_image_path(request)
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


def _resolve_image_path(request: OCRRequest) -> Path | None:
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


def _latex_ocr_model_config() -> dict[str, object]:
    more_processor_configs: dict[str, object] = {"use_fast": True}
    more_model_configs: dict[str, object] = {
        "use_cache": False,
        "encoder_file_name": "encoder_model.onnx",
        "decoder_file_name": "decoder_model.onnx",
    }

    return {
        "model_backend": "onnx",
        "device": None,
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
