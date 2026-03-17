from __future__ import annotations

import base64
import os
import re
from typing import Any

from .base import OCRRequest
from .multimodal_llm import BaseMultimodalLLMOCRPipeline

_GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
_GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"
_KEY_RE = re.compile(r"AIza[0-9A-Za-z_-]{35}")
_BLOCKED_FINISH_REASONS = frozenset(
    {
        "SAFETY",
        "BLOCKLIST",
        "PROHIBITED_CONTENT",
        "SPII",
        "RECITATION",
        "MODEL_ARMOR",
        "IMAGE_SAFETY",
    }
)


class GeminiOCRPipeline(BaseMultimodalLLMOCRPipeline):
    """OCR pipeline backed by the Google Gemini API."""

    provider_name = "Gemini"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        """Initialize a Gemini-backed OCR pipeline.

        Args:
            model: Gemini model name to use for OCR.
            api_key: Optional explicit API key for the Gemini client.
            client: Optional prebuilt client, mainly for tests.

        Returns:
            ``None``. The pipeline stores the model and client.
        """
        super().__init__(model=model)
        self._client = client or self._build_client(api_key=api_key)

    def _build_client(self, *, api_key: str | None):
        """Create a Gemini client using an explicit or environment API key.

        Args:
            api_key: Optional explicit API key override.

        Returns:
            A configured Gemini client instance.
        """
        resolved_api_key = (
            api_key
            or os.getenv(_GEMINI_API_KEY_ENV)
            or os.getenv(_GOOGLE_API_KEY_ENV)
        )
        if not resolved_api_key:
            raise ValueError(
                f"{_GEMINI_API_KEY_ENV} or {_GOOGLE_API_KEY_ENV} environment "
                "variable is required when using GeminiOCRPipeline without an explicit "
                "api_key."
            )

        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - optional dependency.
            raise RuntimeError(
                "Google GenAI SDK is not installed. Install it with "
                "`pip install nb2wb[gemini]` or `pip install google-genai` "
                "to enable Gemini OCR."
            ) from exc

        return genai.Client(api_key=resolved_api_key)

    def _create_response(self, request: OCRRequest):
        """Submit the OCR prompt and image to Gemini.

        Args:
            request: OCR metadata and image source information.

        Returns:
            The raw Gemini API result object.
        """
        image_bytes, mime_type = self.read_image_bytes(request)
        payload = base64.b64encode(image_bytes).decode("ascii")
        try:
            return self._client.models.generate_content(
                model=self.model,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {"text": self._build_prompt()},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": payload,
                                }
                            },
                        ],
                    }
                ],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": self._response_schema(),
                },
            )
        except Exception as exc:  # pragma: no cover - exercised via stubs/tests.
            message = self._sanitize_error_message(str(exc))
            detail = f": {message}" if message else ""
            raise RuntimeError(
                f"Gemini OCR request failed for model '{self.model}'{detail}"
            ) from exc

    def _extract_response_text(self, response: Any) -> str:
        """Extract structured JSON text from a Gemini response.

        Args:
            response: Raw response object or dict returned by Gemini.

        Returns:
            Structured output text, or an empty string when absent.
        """
        text = self._extract_text_value(response)
        if text:
            return text

        candidates = _value_for(response, "candidates")
        if isinstance(candidates, list):
            for candidate in candidates:
                text = self._extract_candidate_text(candidate)
                if text:
                    return text
        return ""

    def _extract_refusal(self, response: Any) -> str:
        """Extract refusal details from a Gemini response when present.

        Args:
            response: Raw response object or dict returned by Gemini.

        Returns:
            Refusal text, or an empty string when the response was accepted.
        """
        prompt_feedback = _value_for(response, "prompt_feedback")
        block_reason = self._extract_prompt_block_reason(prompt_feedback)
        if block_reason:
            return block_reason

        candidates = _value_for(response, "candidates")
        if isinstance(candidates, list):
            for candidate in candidates:
                finish_reason = self._normalize_reason(
                    _value_for(candidate, "finish_reason")
                )
                if finish_reason in _BLOCKED_FINISH_REASONS:
                    text = self._extract_candidate_text(candidate)
                    if text:
                        return text
                    return finish_reason
        return ""

    def _extract_candidate_text(self, candidate: Any) -> str:
        """Extract text from one candidate payload.

        Args:
            candidate: Candidate object or dict from the Gemini response.

        Returns:
            Candidate text, or an empty string when absent.
        """
        text = self._extract_text_value(candidate)
        if text:
            return text

        content = _value_for(candidate, "content")
        parts = _value_for(content, "parts")
        if isinstance(parts, list):
            for part in parts:
                text = self._extract_text_value(part)
                if text:
                    return text
        return ""

    def _extract_prompt_block_reason(self, prompt_feedback: Any) -> str:
        """Build a refusal message from prompt-feedback fields.

        Args:
            prompt_feedback: Prompt-feedback object or dict from Gemini.

        Returns:
            Refusal reason text, or an empty string when not blocked.
        """
        reason = self._normalize_reason(_value_for(prompt_feedback, "block_reason"))
        if not reason or reason == "BLOCK_REASON_UNSPECIFIED":
            return ""
        message = _value_for(prompt_feedback, "block_reason_message")
        if isinstance(message, str) and message.strip():
            return f"{reason}: {message.strip()}"
        return reason

    def _extract_text_value(self, source: Any) -> str:
        """Extract a non-empty text field from an object or mapping.

        Args:
            source: Object or dict potentially containing a ``text`` field.

        Returns:
            Trimmed text content, or an empty string when unavailable.
        """
        text = _value_for(source, "text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        return ""

    def _normalize_reason(self, reason: Any) -> str:
        """Normalize finish/block reasons across enum and string values.

        Args:
            reason: Finish/block reason enum, string, or ``None``.

        Returns:
            An uppercase normalized reason string, or an empty string.
        """
        if reason is None:
            return ""
        enum_name = getattr(reason, "name", None)
        if isinstance(enum_name, str) and enum_name.strip():
            return enum_name.strip().upper()
        return str(reason).strip().upper()

    def _sanitize_error_message(self, message: str) -> str:
        """Redact API key-like strings from surfaced SDK errors.

        Args:
            message: Raw SDK or transport error text.

        Returns:
            Sanitized error text safe to include in exceptions.
        """
        return _KEY_RE.sub("[REDACTED]", message).strip()

    def _response_schema(self) -> dict[str, Any]:
        """Return a Gemini-compatible schema for structured OCR responses.

        Args:
            None.

        Returns:
            A JSON-schema mapping compatible with Gemini response constraints.

        The Gemini API currently rejects ``additionalProperties`` inside
        ``response_schema``. We keep the shared object shape while removing
        that field for this provider.
        """
        schema = super()._response_schema().copy()
        schema.pop("additionalProperties", None)
        return schema


def _value_for(source: Any, name: str) -> Any:
    """Read one attribute/key from objects and dictionaries.

    Args:
        source: Object or dict containing structured response data.
        name: Attribute or key name to read.

    Returns:
        The resolved value when present, otherwise ``None``.
    """
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


__all__ = [
    "GeminiOCRPipeline",
    "OCRRequest",
]
