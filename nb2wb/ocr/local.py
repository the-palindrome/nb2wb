from __future__ import annotations

import base64
import binascii
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from pathlib import PurePosixPath
from tempfile import NamedTemporaryFile, TemporaryDirectory
from urllib.parse import unquote, urlparse

from ..reverse_images import infer_supported_language_from_parts


@dataclass(frozen=True)
class OCRRequest:
    src: str
    alt: str = ""
    title: str = ""
    classes: tuple[str, ...] = ()
    caption: str = ""
    nearby_text: str = ""
    source_dir: Path | None = None


_LATEX_HINTS = ("math", "latex", "equation", "formula")
_CODE_HINTS = ("code", "snippet", "source", "terminal")
_TABLE_HINTS = ("table", "tabular", "dataframe", "grid")


def local_ocr_pipeline(request: OCRRequest) -> dict[str, str]:
    """Default local OCR pipeline backed by Pix2Text and Tesseract."""
    classification = _classify_image(request)
    if classification == "code":
        try:
            image = _load_image(request)
            result = _run_code_ocr(image)
        except Exception:
            return {"type": "figure", "payload": ""}

        if not result:
            return {"type": "figure", "payload": ""}
        return {"type": "code", "payload": result}

    if classification == "table":
        try:
            model = _load_page_ocr_model()
            with _pix2text_input_path(request) as image_path:
                result = _run_table_ocr(model, image_path)
        except Exception:
            return {"type": "figure", "payload": ""}

        if not result:
            return {"type": "figure", "payload": ""}
        return {"type": "table", "payload": result}

    if classification != "latex":
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


def _classify_image(request: OCRRequest) -> str:
    haystack = _classification_haystack(request)
    if any(hint in haystack for hint in _LATEX_HINTS):
        return "latex"
    if any(hint in haystack for hint in _CODE_HINTS):
        return "code"
    if any(hint in haystack for hint in _TABLE_HINTS):
        return "table"
    if infer_supported_language_from_parts(_candidate_texts(request)) is not None:
        return "code"
    return "figure"


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


@lru_cache(maxsize=1)
def _load_page_ocr_model():
    try:
        from pix2text import Pix2Text
    except ImportError as exc:  # pragma: no cover - depends on optional dependency.
        raise RuntimeError(
            "Pix2Text is not installed. Install it with `pip install nb2wb[ocr]` "
            "or `pip install pix2text` to enable table OCR."
        ) from exc

    config = _page_ocr_model_config()
    from_config = getattr(Pix2Text, "from_config", None)
    if callable(from_config):
        try:
            return from_config(total_configs=config)
        except TypeError:
            try:
                return from_config(**config)
            except TypeError:
                pass
    return Pix2Text(**config)


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
        raise ValueError("remote image URLs are not supported for OCR")
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
        raise FileNotFoundError(f"image '{resolved}' not found for OCR")
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


def _page_ocr_model_config() -> dict[str, object]:
    return {
        "enable_table": True,
    }


def _run_latex_ocr(model, image_path: str) -> str:
    if hasattr(model, "recognize"):
        result = model.recognize(image_path, use_post_process=True)
        return _normalize_latex_ocr_result(result)
    return _normalize_latex_ocr_result(model(image_path))


def _run_table_ocr(model, image_path: str) -> str:
    if hasattr(model, "recognize_page"):
        result = model.recognize_page(image_path, page_id="0")
        return _normalize_page_ocr_result(result)
    if hasattr(model, "recognize"):
        result = model.recognize(image_path)
        return _normalize_page_ocr_result(result)
    return ""


def _run_code_ocr(image) -> str:
    try:
        import pytesseract
    except ImportError as exc:  # pragma: no cover - depends on optional dependency.
        raise RuntimeError(
            "pytesseract is not installed. Install it with `pip install nb2wb[ocr]` "
            "or `pip install pytesseract`, and ensure the `tesseract` binary is "
            "available on PATH to enable code OCR."
        ) from exc

    processed = _prepare_code_image_for_ocr(image)
    result = pytesseract.image_to_string(
        processed,
        config="--psm 6 -c preserve_interword_spaces=1",
    )
    return _normalize_code_ocr_result(result)


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


def _normalize_page_ocr_result(result) -> str:
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        for key in ("markdown", "text", "result"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    to_markdown = getattr(result, "to_markdown", None)
    if callable(to_markdown):
        direct = _call_to_markdown(to_markdown)
        if direct:
            return direct
    markdown = getattr(result, "markdown", None)
    if isinstance(markdown, str) and markdown.strip():
        return markdown.strip()
    text = getattr(result, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    return str(result).strip()


def _normalize_code_ocr_result(result) -> str:
    text = str(result).replace("\r\n", "\n").strip()
    text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    return text


def _prepare_code_image_for_ocr(image):
    grayscale = image.convert("L")
    return grayscale.point(lambda value: 255 if value > 180 else 0, mode="1")


def _call_to_markdown(to_markdown) -> str:
    try:
        result = to_markdown()
    except TypeError:
        with TemporaryDirectory() as tmpdir:
            try:
                result = to_markdown(tmpdir)
            except TypeError:
                return ""
            return _normalize_markdown_artifact(result, fallback_dir=Path(tmpdir))
    return _normalize_markdown_artifact(result)


def _normalize_markdown_artifact(result, fallback_dir: Path | None = None) -> str:
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, Path):
        if result.is_file():
            return result.read_text(encoding="utf-8").strip()
        if result.is_dir():
            fallback_dir = result
    if fallback_dir is not None and fallback_dir.exists():
        for candidate in (
            fallback_dir / "output.md",
            fallback_dir / "page.md",
            fallback_dir / "0.md",
        ):
            if candidate.exists():
                text = candidate.read_text(encoding="utf-8").strip()
                if text:
                    return text
    return ""


def _classification_haystack(request: OCRRequest) -> str:
    return " ".join(_candidate_texts(request)).lower()


def _candidate_texts(request: OCRRequest) -> list[str]:
    filename = _filename_from_src(request.src)
    parts = [
        request.alt,
        request.title,
        request.caption,
        request.nearby_text,
        " ".join(request.classes),
        filename,
    ]
    return [part for part in parts if part]


def _filename_from_src(src: str) -> str:
    if not src:
        return ""
    parsed = urlparse(src)
    path = parsed.path or src
    return unquote(PurePosixPath(path).name)


__all__ = [
    "OCRRequest",
    "local_ocr_pipeline",
]
