from __future__ import annotations

import json
import os
import re
from typing import Any

from .base import BaseOCRPipeline, OCRRequest

_OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
_KEY_RE = re.compile(r"sk-[A-Za-z0-9_-]+")


class OpenAIOCRPipeline(BaseOCRPipeline):
    """OCR pipeline backed by the OpenAI Responses API."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        """Initialize an OpenAI-backed OCR pipeline.

        Args:
            model: Responses API model name to use for OCR.
            api_key: Optional explicit API key for the OpenAI client.
            client: Optional prebuilt client, mainly for tests.

        Returns:
            ``None``. The pipeline stores the model and client.
        """
        normalized_model = model.strip()
        if not normalized_model:
            raise ValueError("model is required for OpenAIOCRPipeline")

        self.model = normalized_model
        self._client = client or self._build_client(api_key=api_key)

    def __call__(self, request: OCRRequest) -> dict[str, str]:
        """Run OCR against one image using the OpenAI Responses API.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A result mapping containing the inferred content type and text.
        """
        data_url = self.image_data_url(request)
        response = self._create_response(data_url)
        return self._parse_response(response)

    def _build_client(self, *, api_key: str | None):
        """Create an OpenAI client using the provided or environment API key.

        Args:
            api_key: Optional explicit API key override.

        Returns:
            A configured OpenAI client instance.
        """
        resolved_api_key = api_key or os.getenv(_OPENAI_API_KEY_ENV)
        if not resolved_api_key:
            raise ValueError(
                f"{_OPENAI_API_KEY_ENV} environment variable is required when "
                "using OpenAIOCRPipeline without an explicit api_key."
            )

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency.
            raise RuntimeError(
                "OpenAI SDK is not installed. Install it with `pip install nb2wb[openai]` "
                "or `pip install openai` to enable OpenAI OCR."
            ) from exc

        return OpenAI(api_key=resolved_api_key)

    def _create_response(self, image_data_url: str):
        """Submit the OCR prompt and image to the Responses API.

        Args:
            image_data_url: Base64 data URL for the source image.

        Returns:
            The raw Responses API result object.
        """
        try:
            return self._client.responses.create(
                model=self.model,
                instructions=self._build_prompt(),
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_image",
                                "image_url": image_data_url,
                                "detail": "high",
                            }
                        ],
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "ocr_result",
                        "strict": True,
                        "schema": self._response_schema(),
                    }
                },
            )
        except Exception as exc:  # pragma: no cover - exercised via stubs/tests.
            message = self._sanitize_error_message(str(exc))
            detail = f": {message}" if message else ""
            raise RuntimeError(
                f"OpenAI OCR request failed for model '{self.model}'{detail}"
            ) from exc

    def _parse_response(self, response: Any) -> dict[str, str]:
        """Validate and normalize a Responses API OCR result.

        Args:
            response: Raw response object or dict returned by the API.

        Returns:
            A validated ``{"type", "payload"}`` OCR result mapping.
        """
        refusal = self._extract_refusal(response)
        if refusal:
            raise RuntimeError(f"OpenAI OCR request was refused: {refusal}")

        payload_text = self._extract_response_text(response)
        if not payload_text:
            raise RuntimeError("OpenAI OCR response did not include structured output.")

        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenAI OCR response returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("OpenAI OCR response JSON must be an object.")

        result_type = payload.get("type")
        result_payload = payload.get("payload")
        allowed_types = {"latex", "code", "table", "figure"}
        if result_type not in allowed_types:
            allowed = ", ".join(sorted(allowed_types))
            raise RuntimeError(
                f"OpenAI OCR response type must be one of: {allowed}"
            )
        if not isinstance(result_payload, str):
            raise RuntimeError("OpenAI OCR response payload must be a string.")
        if result_type == "figure" and result_payload != "":
            raise RuntimeError("OpenAI OCR response figure payload must be empty.")

        return {"type": result_type, "payload": result_payload}

    def _extract_response_text(self, response: Any) -> str:
        """Extract the structured JSON text payload from an OCR response.

        Args:
            response: Raw response object or dict returned by the API.

        Returns:
            Structured output text, or an empty string when absent.
        """
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        output = getattr(response, "output", None)
        if isinstance(output, list):
            for item in output:
                if not self._is_message_item(item):
                    continue
                content = getattr(item, "content", None)
                if isinstance(content, list):
                    for chunk in content:
                        text = self._extract_text_chunk(chunk)
                        if text:
                            return text

        if isinstance(response, dict):
            output_text = response.get("output_text")
            if isinstance(output_text, str) and output_text.strip():
                return output_text.strip()
            output = response.get("output")
            if isinstance(output, list):
                for item in output:
                    if not isinstance(item, dict) or item.get("type") != "message":
                        continue
                    content = item.get("content")
                    if isinstance(content, list):
                        for chunk in content:
                            text = self._extract_text_chunk(chunk)
                            if text:
                                return text

        return ""

    def _extract_refusal(self, response: Any) -> str:
        """Extract refusal text from an OCR response when present.

        Args:
            response: Raw response object or dict returned by the API.

        Returns:
            Refusal text, or an empty string when the response was accepted.
        """
        output = getattr(response, "output", None)
        if isinstance(output, list):
            for item in output:
                if not self._is_message_item(item):
                    continue
                content = getattr(item, "content", None)
                if isinstance(content, list):
                    for chunk in content:
                        refusal = self._extract_refusal_chunk(chunk)
                        if refusal:
                            return refusal

        if isinstance(response, dict):
            output = response.get("output")
            if isinstance(output, list):
                for item in output:
                    if not isinstance(item, dict) or item.get("type") != "message":
                        continue
                    content = item.get("content")
                    if isinstance(content, list):
                        for chunk in content:
                            refusal = self._extract_refusal_chunk(chunk)
                            if refusal:
                                return refusal

        return ""

    def _is_message_item(self, item: Any) -> bool:
        """Check whether a response output item is a message container.

        Args:
            item: Response output item to inspect.

        Returns:
            ``True`` when the item represents a message object.
        """
        if isinstance(item, dict):
            return item.get("type") == "message"
        return getattr(item, "type", None) == "message"

    def _extract_text_chunk(self, chunk: Any) -> str:
        """Extract text from one response content chunk.

        Args:
            chunk: Content chunk object or dict from the response.

        Returns:
            Chunk text, or an empty string when the chunk is not text.
        """
        if isinstance(chunk, dict):
            chunk_type = chunk.get("type")
            if chunk_type in {"output_text", "text"}:
                text = chunk.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
        else:
            chunk_type = getattr(chunk, "type", None)
            if chunk_type in {"output_text", "text"}:
                text = getattr(chunk, "text", None)
                if isinstance(text, str) and text.strip():
                    return text.strip()
        return ""

    def _extract_refusal_chunk(self, chunk: Any) -> str:
        """Extract refusal text from one response content chunk.

        Args:
            chunk: Content chunk object or dict from the response.

        Returns:
            Refusal text, or an empty string when absent.
        """
        if isinstance(chunk, dict):
            if chunk.get("type") == "refusal":
                refusal = chunk.get("refusal")
                if isinstance(refusal, str) and refusal.strip():
                    return refusal.strip()
        else:
            if getattr(chunk, "type", None) == "refusal":
                refusal = getattr(chunk, "refusal", None)
                if isinstance(refusal, str) and refusal.strip():
                    return refusal.strip()
        return ""

    def _build_prompt(self) -> str:
        """Build the OCR classification prompt sent to the model.

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
        """Redact API key-like strings from surfaced SDK errors.

        Args:
            message: Raw error message text from the SDK or transport layer.

        Returns:
            Sanitized error text safe to include in exceptions.
        """
        redacted = _KEY_RE.sub("[REDACTED]", message).strip()
        return redacted


__all__ = [
    "OpenAIOCRPipeline",
    "OCRRequest",
]
