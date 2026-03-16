from __future__ import annotations

from .local import OCRRequest


def multimodal_llm_pipeline(request: OCRRequest) -> dict[str, str]:
    """Placeholder multimodal OCR pipeline."""
    _ = request
    return {"type": "figure", "payload": ""}


__all__ = [
    "OCRRequest",
    "multimodal_llm_pipeline",
]
