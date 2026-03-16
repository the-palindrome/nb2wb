from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory

from ..reverse_images import infer_supported_language_from_parts
from .base import BaseOCRPipeline, OCRRequest

_LATEX_HINTS = ("math", "latex", "equation", "formula")
_CODE_HINTS = ("code", "snippet", "source", "terminal")
_TABLE_HINTS = ("table", "tabular", "dataframe", "grid")


class LocalOCRPipeline(BaseOCRPipeline):
    """Local OCR pipeline backed by Pix2Text and Tesseract."""

    def __call__(self, request: OCRRequest) -> dict[str, str]:
        classification = self.classify_image(request)
        if classification == "code":
            try:
                image = self.load_image(request)
                result = self._run_code_ocr(image)
            except Exception:
                return {"type": "figure", "payload": ""}

            if not result:
                return {"type": "figure", "payload": ""}
            return {"type": "code", "payload": result}

        if classification == "table":
            try:
                model = self._load_page_ocr_model()
                with self.input_image_path(request) as image_path:
                    result = self._run_table_ocr(model, image_path)
            except Exception:
                return {"type": "figure", "payload": ""}

            if not result:
                return {"type": "figure", "payload": ""}
            return {"type": "table", "payload": result}

        if classification != "latex":
            return {"type": "figure", "payload": ""}

        try:
            model = self._load_latex_ocr_model()
            with self.input_image_path(request) as image_path:
                result = self._run_latex_ocr(model, image_path)
        except Exception:
            return {"type": "figure", "payload": ""}

        if not result:
            return {"type": "figure", "payload": ""}
        return {"type": "latex", "payload": result}

    def classify_image(self, request: OCRRequest) -> str:
        haystack = self.classification_haystack(request)
        if any(hint in haystack for hint in _LATEX_HINTS):
            return "latex"
        if any(hint in haystack for hint in _CODE_HINTS):
            return "code"
        if any(hint in haystack for hint in _TABLE_HINTS):
            return "table"
        if infer_supported_language_from_parts(self.candidate_texts(request)) is not None:
            return "code"
        return "figure"

    @lru_cache(maxsize=1)
    def _load_latex_ocr_model(self):
        try:
            from pix2text.latex_ocr import LatexOCR
        except ImportError as exc:  # pragma: no cover - depends on optional dependency.
            raise RuntimeError(
                "Pix2Text is not installed. Install it with `pip install nb2wb[ocr]` "
                "or `pip install pix2text` to enable LaTeX OCR."
            ) from exc
        return LatexOCR(**_latex_ocr_model_config())

    @lru_cache(maxsize=1)
    def _load_page_ocr_model(self):
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

    def _run_latex_ocr(self, model, image_path: str) -> str:
        if hasattr(model, "recognize"):
            result = model.recognize(image_path, use_post_process=True)
            return _normalize_latex_ocr_result(result)
        return _normalize_latex_ocr_result(model(image_path))

    def _run_table_ocr(self, model, image_path: str) -> str:
        if hasattr(model, "recognize_page"):
            result = model.recognize_page(image_path, page_id="0")
            return _normalize_page_ocr_result(result)
        if hasattr(model, "recognize"):
            result = model.recognize(image_path)
            return _normalize_page_ocr_result(result)
        return ""

    def _run_code_ocr(self, image) -> str:
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


local_ocr_pipeline = LocalOCRPipeline()

__all__ = [
    "LocalOCRPipeline",
    "OCRRequest",
    "local_ocr_pipeline",
]
