from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .base import BaseOCRPipeline, OCRRequest

_LIGHT_CODE_PALETTE = (
    (255, 255, 255),
    (36, 41, 47),
    (5, 80, 174),
    (130, 80, 223),
    (207, 34, 46),
    (17, 99, 41),
    (149, 56, 0),
)
_DARK_CODE_PALETTE = (
    (30, 30, 30),
    (212, 212, 212),
    (86, 156, 214),
    (206, 145, 120),
    (220, 220, 170),
    (197, 134, 192),
    (78, 201, 176),
)
_PALETTE_DISTANCE_THRESHOLD = 38
_DARK_BACKGROUND_THRESHOLD = 0.32
_LIGHT_BACKGROUND_THRESHOLD = 0.45
_ACCENT_THRESHOLD = 0.015
_MIN_ACCENT_MATCHES = 2


class LocalOCRPipeline(BaseOCRPipeline):
    """Local OCR pipeline backed by Pix2Text and Tesseract."""

    def __call__(self, request: OCRRequest) -> dict[str, str]:
        """Classify an image and run the matching local OCR pipeline.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A result mapping containing the inferred content type and text.
        """
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
        """Classify an image as code, table, latex, or generic figure.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A classification label used to choose the OCR backend.
        """
        pix2text_classification = self._classify_with_pix2text(request)
        if pix2text_classification is not None:
            return pix2text_classification
        if self._matches_code_histogram(request):
            return "code"
        return "figure"

    def _classify_with_pix2text(self, request: OCRRequest) -> str | None:
        """Ask Pix2Text whether the image looks like a table or formula.

        Args:
            request: OCR metadata and image source information.

        Returns:
            ``table`` or ``latex`` when detected, otherwise ``None``.
        """
        try:
            model = self._load_page_ocr_model()
            with self.input_image_path(request) as image_path:
                page = model.recognize_page(image_path, page_id="0", table_as_image=True)
        except Exception:
            return None

        for element in self._iter_page_elements(page):
            element_type = self._normalize_element_type(element)
            if element_type == "table":
                return "table"
            if element_type == "formula":
                return "latex"
        return None

    def _matches_code_histogram(self, request: OCRRequest) -> bool:
        """Heuristically detect code screenshots from their color palette.

        Args:
            request: OCR metadata and image source information.

        Returns:
            ``True`` when the image resembles a code editor screenshot.
        """
        try:
            image = self.load_image(request)
        except Exception:
            return False

        samples = image.convert("RGB").resize((96, 96))
        total = samples.width * samples.height
        if total == 0:
            return False

        light_matches = self._palette_match_ratios(samples, _LIGHT_CODE_PALETTE)
        dark_matches = self._palette_match_ratios(samples, _DARK_CODE_PALETTE)
        return self._is_code_palette_match(
            light_matches,
            background_threshold=_LIGHT_BACKGROUND_THRESHOLD,
        ) or self._is_code_palette_match(
            dark_matches,
            background_threshold=_DARK_BACKGROUND_THRESHOLD,
        )

    def _palette_match_ratios(
        self,
        image,
        palette: tuple[tuple[int, int, int], ...],
    ) -> list[float]:
        """Measure how closely image pixels match a reference color palette.

        Args:
            image: Pillow image to sample.
            palette: Ordered RGB palette to compare against.

        Returns:
            Match ratios for each palette color across the sampled image.
        """
        counts = [0] * len(palette)
        pixels = image.load()
        total = image.width * image.height
        for y in range(image.height):
            for x in range(image.width):
                pixel = pixels[x, y]
                best_index = None
                best_distance = None
                for index, color in enumerate(palette):
                    distance = self._color_distance(pixel, color)
                    if best_distance is None or distance < best_distance:
                        best_index = index
                        best_distance = distance
                if best_index is not None and best_distance is not None:
                    if best_distance <= _PALETTE_DISTANCE_THRESHOLD:
                        counts[best_index] += 1
        return [count / total for count in counts]

    def _is_code_palette_match(
        self,
        match_ratios: list[float],
        *,
        background_threshold: float,
    ) -> bool:
        """Decide whether palette-match ratios look like a code screenshot.

        Args:
            match_ratios: Pixel-match ratios for the reference palette.
            background_threshold: Minimum background ratio required for a hit.

        Returns:
            ``True`` when the ratios satisfy the code-image heuristic.
        """
        background_ratio = match_ratios[0]
        foreground_ratio = match_ratios[1]
        accent_hits = sum(1 for ratio in match_ratios[2:] if ratio >= _ACCENT_THRESHOLD)
        return (
            background_ratio >= background_threshold
            and foreground_ratio >= 0.02
            and accent_hits >= _MIN_ACCENT_MATCHES
        )

    def _color_distance(
        self,
        left: tuple[int, int, int],
        right: tuple[int, int, int],
    ) -> float:
        """Compute Euclidean distance between two RGB colors.

        Args:
            left: First RGB color tuple.
            right: Second RGB color tuple.

        Returns:
            Numeric color distance between the two tuples.
        """
        return (
            ((left[0] - right[0]) ** 2)
            + ((left[1] - right[1]) ** 2)
            + ((left[2] - right[2]) ** 2)
        ) ** 0.5

    def _iter_page_elements(self, page: Any) -> list[Any]:
        """Extract page elements from Pix2Text page results.

        Args:
            page: Pix2Text response object or dict-like payload.

        Returns:
            A list of detected page elements, or an empty list.
        """
        elements = getattr(page, "elements", None)
        if isinstance(elements, list):
            return elements
        if isinstance(page, dict):
            raw_elements = page.get("elements")
            if isinstance(raw_elements, list):
                return raw_elements
        return []

    def _normalize_element_type(self, element: Any) -> str | None:
        """Normalize Pix2Text element types to the pipeline's labels.

        Args:
            element: Pix2Text element object or dict-like payload.

        Returns:
            ``table``, ``formula``, or ``None`` when no mapping applies.
        """
        raw_type = None
        if isinstance(element, dict):
            raw_type = element.get("type")
        else:
            raw_type = getattr(element, "type", None)

        if raw_type is None:
            return None
        if isinstance(raw_type, str):
            normalized = raw_type.lower()
        else:
            normalized = str(raw_type).split(".")[-1].lower()

        if "table" in normalized:
            return "table"
        if "formula" in normalized or normalized in {"isolated", "embedding"}:
            return "formula"
        return None

    @lru_cache(maxsize=1)
    def _load_latex_ocr_model(self):
        """Create and cache the Pix2Text LaTeX OCR model.

        Args:
            None.

        Returns:
            A configured Pix2Text LaTeX OCR model instance.
        """
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
        """Create and cache the Pix2Text page OCR model.

        Args:
            None.

        Returns:
            A configured Pix2Text page OCR model instance.
        """
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
        """Run LaTeX OCR against an image file path.

        Args:
            model: Loaded LaTeX OCR model instance.
            image_path: Filesystem path to the source image.

        Returns:
            Normalized LaTeX text extracted from the image.
        """
        if hasattr(model, "recognize"):
            result = model.recognize(image_path, use_post_process=True)
            return _normalize_latex_ocr_result(result)
        return _normalize_latex_ocr_result(model(image_path))

    def _run_table_ocr(self, model, image_path: str) -> str:
        """Run page/table OCR against an image file path.

        Args:
            model: Loaded page OCR model instance.
            image_path: Filesystem path to the source image.

        Returns:
            Normalized markdown or text extracted from the table image.
        """
        if hasattr(model, "recognize_page"):
            result = model.recognize_page(image_path, page_id="0")
            return _normalize_page_ocr_result(result)
        if hasattr(model, "recognize"):
            result = model.recognize(image_path)
            return _normalize_page_ocr_result(result)
        return ""

    def _run_code_ocr(self, image) -> str:
        """Run Tesseract OCR against a code screenshot image.

        Args:
            image: Pillow image containing a code screenshot.

        Returns:
            Normalized source text extracted from the image.
        """
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
    """Build configuration kwargs for the Pix2Text LaTeX model.

    Args:
        None.

    Returns:
        A mapping of model and processor configuration values.
    """
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
    """Build configuration kwargs for the Pix2Text page model.

    Args:
        None.

    Returns:
        A mapping of page-model configuration values.
    """
    return {
        "enable_table": True,
    }


def _normalize_latex_ocr_result(result) -> str:
    """Normalize LaTeX OCR output from different backend return shapes.

    Args:
        result: OCR backend result object, string, mapping, or list.

    Returns:
        Cleaned LaTeX text extracted from the result.
    """
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
    """Normalize page OCR output into a plain markdown or text string.

    Args:
        result: OCR backend result object, string, mapping, or model output.

    Returns:
        Cleaned markdown or text extracted from the result.
    """
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
    """Normalize raw Tesseract output for code snippets.

    Args:
        result: OCR result object or string returned by Tesseract.

    Returns:
        Cleaned code text with normalized line endings.
    """
    text = str(result).replace("\r\n", "\n").strip()
    text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    return text


def _prepare_code_image_for_ocr(image):
    """Convert a code screenshot into a high-contrast OCR-friendly image.

    Args:
        image: Pillow image containing a code screenshot.

    Returns:
        A binarized Pillow image optimized for text extraction.
    """
    grayscale = image.convert("L")
    return grayscale.point(lambda value: 255 if value > 180 else 0, mode="1")


def _call_to_markdown(to_markdown) -> str:
    """Call a backend ``to_markdown`` helper with flexible signatures.

    Args:
        to_markdown: Callable returning markdown directly or via a temp dir.

    Returns:
        Normalized markdown text, or an empty string on signature mismatch.
    """
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
    """Resolve markdown text from backend return values or artifact files.

    Args:
        result: Backend return value, path, or directory-like artifact.
        fallback_dir: Optional directory to search for generated markdown.

    Returns:
        Extracted markdown text, or an empty string when unavailable.
    """
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
