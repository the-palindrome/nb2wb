from __future__ import annotations

from nb2wb.reverse_images import _latex_ocr_model_config, normalize_ocr_device


class TestReverseImages:
    def test_normalize_ocr_device_auto_defaults_to_none(self):
        assert normalize_ocr_device(None) is None
        assert normalize_ocr_device("auto") is None

    def test_latex_ocr_model_config_prefers_onnx_and_fast_processor(self):
        config = _latex_ocr_model_config(None)

        assert config["model_backend"] == "onnx"
        assert config["device"] is None
        assert config["more_processor_configs"] == {"use_fast": True}
        assert config["more_model_configs"]["use_cache"] is False
        assert config["more_model_configs"]["encoder_file_name"] == "encoder_model.onnx"
        assert config["more_model_configs"]["decoder_file_name"] == "decoder_model.onnx"
        assert "provider" not in config["more_model_configs"]

    def test_latex_ocr_model_config_uses_cuda_provider_when_requested(self):
        config = _latex_ocr_model_config("cuda")

        assert config["model_backend"] == "onnx"
        assert config["more_model_configs"]["provider"] == "CUDAExecutionProvider"

    def test_latex_ocr_model_config_falls_back_to_pytorch_for_mps(self):
        config = _latex_ocr_model_config("mps")

        assert config["model_backend"] == "pytorch"
        assert config["more_processor_configs"] == {"use_fast": True}
        assert config["more_model_configs"] == {"use_cache": False}
