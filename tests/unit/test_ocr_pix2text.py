from __future__ import annotations

from pathlib import Path
import tempfile

from PIL import Image

import nb2wb.ocr.local as local_module
from nb2wb.ocr.local import (
    OCRRequest,
    _latex_ocr_model_config,
    _page_ocr_model_config,
    local_ocr_pipeline,
)
from nb2wb.ocr.multimodal_llm import multimodal_llm_pipeline


class TestLocalOcrPipeline:
    def test_multimodal_llm_pipeline_is_placeholder(self):
        result = multimodal_llm_pipeline(OCRRequest(src="chart.png", alt="Chart"))

        assert result == {"type": "figure", "payload": ""}

    def test_latex_ocr_model_config_prefers_onnx_and_fast_processor(self):
        config = _latex_ocr_model_config()

        assert config["model_backend"] == "onnx"
        assert config["device"] is None
        assert config["more_processor_configs"] == {"use_fast": True}
        assert config["more_model_configs"]["use_cache"] is False
        assert config["more_model_configs"]["encoder_file_name"] == "encoder_model.onnx"
        assert config["more_model_configs"]["decoder_file_name"] == "decoder_model.onnx"

    def test_page_ocr_model_config_enables_table_recognition(self):
        config = _page_ocr_model_config()

        assert config["enable_table"] is True

    def test_pipeline_returns_latex_for_successful_recognition(self, monkeypatch):
        class StubLatexOCR:
            def recognize(self, image_path, use_post_process=True):
                return {"text": r"\alpha + \beta"}

        monkeypatch.setattr(local_module, "_load_latex_ocr_model", lambda: StubLatexOCR())

        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "eq.png"
            Image.new("RGB", (4, 4), color="white").save(image_path)
            result = local_ocr_pipeline(
                OCRRequest(src="eq.png", alt="LaTeX equation", source_dir=Path(td))
            )

        assert result == {"type": "latex", "payload": r"\alpha + \beta"}

    def test_pipeline_returns_figure_when_recognition_fails(self, monkeypatch):
        monkeypatch.setattr(
            local_module,
            "_load_latex_ocr_model",
            lambda: (_ for _ in ()).throw(RuntimeError("no model")),
        )

        result = local_ocr_pipeline(
            OCRRequest(src="eq.png", alt="LaTeX equation", source_dir=Path("."))
        )

        assert result == {"type": "figure", "payload": ""}

    def test_pipeline_returns_figure_for_code_like_images_without_code_ocr(self):
        result = local_ocr_pipeline(
            OCRRequest(
                src="snippet.png",
                alt="Python code snippet",
                classes=("code-snippet", "language-python"),
                source_dir=Path("."),
            )
        )

        assert result == {"type": "figure", "payload": ""}

    def test_pipeline_returns_code_for_successful_tesseract_recognition(self, monkeypatch):
        monkeypatch.setattr(
            local_module,
            "_run_code_ocr",
            lambda image: "print(42)\nvalue = 1",
        )

        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "snippet.png"
            Image.new("RGB", (4, 4), color="white").save(image_path)
            result = local_ocr_pipeline(
                OCRRequest(
                    src="snippet.png",
                    alt="Python code snippet",
                    classes=("code-snippet", "language-python"),
                    source_dir=Path(td),
                )
            )

        assert result == {"type": "code", "payload": "print(42)\nvalue = 1"}

    def test_pipeline_returns_table_for_successful_table_recognition(self, monkeypatch):
        class StubPageOCR:
            def recognize_page(self, image_path, page_id="0"):
                return {"markdown": "|A|B|\n|-|-|\n|1|2|"}

        monkeypatch.setattr(local_module, "_load_page_ocr_model", lambda: StubPageOCR())

        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "table.png"
            Image.new("RGB", (4, 4), color="white").save(image_path)
            result = local_ocr_pipeline(
                OCRRequest(
                    src="table.png",
                    alt="Model comparison table",
                    classes=("table",),
                    source_dir=Path(td),
                )
            )

        assert result == {"type": "table", "payload": "|A|B|\n|-|-|\n|1|2|"}

    def test_pipeline_returns_figure_for_regular_images(self):
        result = local_ocr_pipeline(
            OCRRequest(src="chart.png", alt="Line chart", source_dir=Path("."))
        )

        assert result == {"type": "figure", "payload": ""}
