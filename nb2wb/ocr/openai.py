from __future__ import annotations

import os
import re
import time
from typing import Any

from .base import OCRRequest
from .multimodal_llm import BaseMultimodalLLMOCRPipeline

_OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
_KEY_RE = re.compile(r"sk-[A-Za-z0-9_-]+")


class OpenAIOCRPipeline(BaseMultimodalLLMOCRPipeline):
    """OCR pipeline backed by the OpenAI Responses API."""

    provider_name = "OpenAI"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        client: Any | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize an OpenAI-backed OCR pipeline.

        Args:
            model: Responses API model name to use for OCR.
            api_key: Optional explicit API key for the OpenAI client.
            client: Optional prebuilt client, mainly for tests.
            verbose: Whether to emit debug logs to stderr during OCR.

        Returns:
            ``None``. The pipeline stores the model and client.
        """
        super().__init__(model=model, verbose=verbose)
        self._client = client or self._build_client(api_key=api_key)

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

    def _create_response(self, request: OCRRequest):
        """Submit the OCR prompt and image to the Responses API.

        Args:
            request: OCR metadata and image source information.

        Returns:
            The raw Responses API result object.
        """
        self._debug("encoding image as data URL")
        encode_started = time.monotonic()
        image_data_url = self.image_data_url(request)
        self._debug(
            "prepared image payload "
            f"in {self._format_duration(time.monotonic() - encode_started)} "
            f"(chars={len(image_data_url)})"
        )
        request_started = time.monotonic()
        self._debug(f"calling responses.create(model={self.model})")
        try:
            response = self._client.responses.create(
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
            self._debug(
                "responses.create returned "
                f"in {self._format_duration(time.monotonic() - request_started)}"
            )
            return response
        except Exception as exc:  # pragma: no cover - exercised via stubs/tests.
            message = self._sanitize_error_message(str(exc))
            detail = f": {message}" if message else ""
            self._debug(
                "responses.create failed "
                f"after {self._format_duration(time.monotonic() - request_started)}"
                f"{detail}"
            )
            raise RuntimeError(
                f"OpenAI OCR request failed for model '{self.model}'{detail}"
            ) from exc

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

    def _sanitize_error_message(self, message: str) -> str:
        """Redact API key-like strings from surfaced SDK errors.

        Args:
            message: Raw error message text from the SDK or transport layer.

        Returns:
            Sanitized error text safe to include in exceptions.
        """
        return _KEY_RE.sub("[REDACTED]", message).strip()


__all__ = [
    "OpenAIOCRPipeline",
    "OCRRequest",
]
