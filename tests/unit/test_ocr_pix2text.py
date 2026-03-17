from __future__ import annotations

from pathlib import Path
import tempfile

from PIL import Image

from nb2wb.ocr.local import (
    OCRRequest,
    _latex_ocr_model_config,
    _page_ocr_model_config,
    local_ocr_pipeline,
)


class TestLocalOcrPipeline:
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
        page_model = type("PageModel", (), {})()
        page_model.recognize_page = (
            lambda image_path, page_id="0", table_as_image=True: {"elements": [{"type": "formula"}]}
        )
        latex_model = type("LatexModel", (), {})()
        latex_model.recognize = (
            lambda image_path, use_post_process=True: {"text": r"\alpha + \beta"}
        )

        monkeypatch.setattr(local_ocr_pipeline, "_load_page_ocr_model", lambda: page_model)
        monkeypatch.setattr(local_ocr_pipeline, "_load_latex_ocr_model", lambda: latex_model)

        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "eq.png"
            Image.new("RGB", (4, 4), color="white").save(image_path)
            result = local_ocr_pipeline(
                OCRRequest(src="eq.png", alt="LaTeX equation", source_dir=Path(td))
            )

        assert result == {"type": "latex", "payload": r"\alpha + \beta"}

    def test_pipeline_returns_figure_when_latex_ocr_fails(self, monkeypatch):
        page_model = type("PageModel", (), {})()
        page_model.recognize_page = (
            lambda image_path, page_id="0", table_as_image=True: {"elements": [{"type": "formula"}]}
        )

        monkeypatch.setattr(local_ocr_pipeline, "_load_page_ocr_model", lambda: page_model)
        monkeypatch.setattr(
            local_ocr_pipeline,
            "_load_latex_ocr_model",
            lambda: (_ for _ in ()).throw(RuntimeError("no model")),
        )

        result = local_ocr_pipeline(
            OCRRequest(src="eq.png", alt="LaTeX equation", source_dir=Path("."))
        )

        assert result == {"type": "figure", "payload": ""}

    def test_pipeline_returns_figure_for_code_like_images_without_histogram_match(self, monkeypatch):
        monkeypatch.setattr(local_ocr_pipeline, "_classify_with_pix2text", lambda request: None)
        monkeypatch.setattr(local_ocr_pipeline, "_matches_code_histogram", lambda request: False)

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
        monkeypatch.setattr(local_ocr_pipeline, "_classify_with_pix2text", lambda request: None)
        monkeypatch.setattr(local_ocr_pipeline, "_matches_code_histogram", lambda request: True)
        monkeypatch.setattr(
            local_ocr_pipeline,
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
        page_model = type("PageModel", (), {})()
        page_model.recognize_page = lambda image_path, page_id="0", table_as_image=True: {
            "elements": [{"type": "table"}],
            "markdown": "|A|B|\n|-|-|\n|1|2|",
        }

        monkeypatch.setattr(local_ocr_pipeline, "_load_page_ocr_model", lambda: page_model)

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

    def test_pipeline_uses_histogram_preclassification_for_code_images(self, monkeypatch):
        monkeypatch.setattr(local_ocr_pipeline, "_classify_with_pix2text", lambda request: None)
        monkeypatch.setattr(local_ocr_pipeline, "_matches_code_histogram", lambda request: True)
        monkeypatch.setattr(local_ocr_pipeline, "_run_code_ocr", lambda image: "print(42)")

        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "snippet.png"
            Image.new("RGB", (4, 4), color="white").save(image_path)
            result = local_ocr_pipeline(
                OCRRequest(src="snippet.png", alt="unknown", source_dir=Path(td))
            )

        assert result == {"type": "code", "payload": "print(42)"}

    def test_pipeline_returns_figure_for_regular_images(self):
        result = local_ocr_pipeline(
            OCRRequest(src="chart.png", alt="Line chart", source_dir=Path("."))
        )

        assert result == {"type": "figure", "payload": ""}
