from __future__ import annotations

import json
from typing import Any

from .base import BaseOCRPipeline, OCRRequest

_ALLOWED_OCR_TYPES = frozenset({"latex", "code", "table", "figure"})


class BaseMultimodalLLMOCRPipeline(BaseOCRPipeline):
    """Shared OCR flow for multimodal LLM providers."""

    provider_name = "LLM"

    def __init__(self, *, model: str) -> None:
        """Store and validate the model name used by the pipeline.

        Args:
            model: Provider model name to use for OCR.

        Returns:
            ``None``. The pipeline stores the normalized model string.
        """
        normalized_model = model.strip()
        if not normalized_model:
            raise ValueError(f"model is required for {self.__class__.__name__}")
        self.model = normalized_model

    def __call__(self, request: OCRRequest) -> dict[str, str]:
        """Run OCR against one image using a multimodal LLM backend.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A validated ``{"type", "payload"}`` OCR result mapping.
        """
        response = self._create_response(request)
        return self._parse_response(response)

    def _create_response(self, request: OCRRequest):
        """Submit an OCR request to the provider backend.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A provider-specific raw response object.
        """
        raise NotImplementedError

    def _parse_response(self, response: Any) -> dict[str, str]:
        """Validate and normalize a multimodal OCR response.

        Args:
            response: Raw response object or dict returned by the provider.

        Returns:
            A validated ``{"type", "payload"}`` OCR result mapping.
        """
        refusal = self._extract_refusal(response)
        if refusal:
            raise RuntimeError(
                f"{self.provider_name} OCR request was refused: {refusal}"
            )

        payload_text = self._extract_response_text(response)
        if not payload_text:
            raise RuntimeError(
                f"{self.provider_name} OCR response did not include structured output."
            )

        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{self.provider_name} OCR response returned invalid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise RuntimeError(
                f"{self.provider_name} OCR response JSON must be an object."
            )

        result_type = payload.get("type")
        result_payload = payload.get("payload")
        if result_type not in _ALLOWED_OCR_TYPES:
            allowed = ", ".join(sorted(_ALLOWED_OCR_TYPES))
            raise RuntimeError(
                f"{self.provider_name} OCR response type must be one of: {allowed}"
            )
        if not isinstance(result_payload, str):
            raise RuntimeError(
                f"{self.provider_name} OCR response payload must be a string."
            )
        if result_type == "figure" and result_payload != "":
            raise RuntimeError(
                f"{self.provider_name} OCR response figure payload must be empty."
            )
        return {"type": result_type, "payload": result_payload}

    def _extract_response_text(self, response: Any) -> str:
        """Extract structured JSON text from a provider response.

        Args:
            response: Raw response object or dict returned by the provider.

        Returns:
            Structured output text, or an empty string when absent.
        """
        raise NotImplementedError

    def _extract_refusal(self, response: Any) -> str:
        """Extract refusal text from a provider response when present.

        Args:
            response: Raw response object or dict returned by the provider.

        Returns:
            Refusal text, or an empty string when the response was accepted.
        """
        return ""

    def _build_prompt(self) -> str:
        """Build the OCR classification prompt sent to the provider model.

        Args:
            None.

        Returns:
            Instruction text describing the expected OCR JSON output.
        """
        return (
            "You are an OCR system that classifies a single image from a technical post. "
            "Return only structured JSON with keys 'type' and 'payload'. "
            "The type must be exactly one of: latex, code, table, figure. "
            "Use 'latex' for equations and mathematical expressions, "
            "'code' for code snippets, 'table' for tabular content, and "
            "'figure' for everything else. "
            "For 'figure', the payload must be an empty string. "
            "For the other types, payload must contain only the extracted source text."
            "Ignore the outputs occasionally displayed on code snippet screenshots."
            "Correctly indent code from code snippet screenshots."
            "Tables must follow markdown syntax."
        )

    def _response_schema(self) -> dict[str, Any]:
        """Return the JSON schema enforced for OCR responses.

        Args:
            None.

        Returns:
            A JSON-schema mapping for the OCR response payload.
        """
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["type", "payload"],
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["latex", "code", "table", "figure"],
                },
                "payload": {"type": "string"},
            },
        }

    def _sanitize_error_message(self, message: str) -> str:
        """Redact or normalize provider SDK errors before surfacing them.

        Args:
            message: Raw error message text from the SDK or transport layer.

        Returns:
            Sanitized error text safe to include in exceptions.
        """
        return message.strip()


__all__ = [
    "BaseMultimodalLLMOCRPipeline",
    "OCRRequest",
]
