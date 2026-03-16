from __future__ import annotations

from .base import BaseOCRPipeline, OCRRequest


class MultimodalLLMPipeline(BaseOCRPipeline):
    """Placeholder multimodal OCR pipeline."""

    def __call__(self, request: OCRRequest) -> dict[str, str]:
        _ = request
        return {"type": "figure", "payload": ""}


multimodal_llm_pipeline = MultimodalLLMPipeline()

__all__ = [
    "MultimodalLLMPipeline",
    "OCRRequest",
    "multimodal_llm_pipeline",
]
