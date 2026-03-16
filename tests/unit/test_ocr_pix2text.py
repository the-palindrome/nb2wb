from __future__ import annotations

from pathlib import Path
import tempfile

from PIL import Image

from nb2wb.ocr.pix2text import OCRRequest, _latex_ocr_model_config, pix2text_ocr_pipeline
import nb2wb.ocr.pix2text as pix2text_module


class TestPix2TextOcrPipeline:
    def test_latex_ocr_model_config_prefers_onnx_and_fast_processor(self):
        config = _latex_ocr_model_config()

        assert config["model_backend"] == "onnx"
        assert config["device"] is None
        assert config["more_processor_configs"] == {"use_fast": True}
        assert config["more_model_configs"]["use_cache"] is False
        assert config["more_model_configs"]["encoder_file_name"] == "encoder_model.onnx"
        assert config["more_model_configs"]["decoder_file_name"] == "decoder_model.onnx"

    def test_pipeline_returns_latex_for_successful_recognition(self, monkeypatch):
        class StubLatexOCR:
            def recognize(self, image_path, use_post_process=True):
                return {"text": r"\alpha + \beta"}

        monkeypatch.setattr(pix2text_module, "_load_latex_ocr_model", lambda: StubLatexOCR())

        with tempfile.TemporaryDirectory() as td:
            image_path = Path(td) / "eq.png"
            Image.new("RGB", (4, 4), color="white").save(image_path)
            result = pix2text_ocr_pipeline(
                OCRRequest(src="eq.png", classification="latex", source_dir=Path(td))
            )

        assert result == {"type": "latex", "payload": r"\alpha + \beta"}

    def test_pipeline_returns_figure_when_recognition_fails(self, monkeypatch):
        monkeypatch.setattr(
            pix2text_module,
            "_load_latex_ocr_model",
            lambda: (_ for _ in ()).throw(RuntimeError("no model")),
        )

        result = pix2text_ocr_pipeline(
            OCRRequest(src="eq.png", classification="latex", source_dir=Path("."))
        )

        assert result == {"type": "figure", "payload": ""}

    def test_pipeline_returns_figure_for_non_latex_classification(self):
        result = pix2text_ocr_pipeline(
            OCRRequest(src="snippet.png", classification="code", source_dir=Path("."))
        )

        assert result == {"type": "figure", "payload": ""}
