from __future__ import annotations

import json
import logging
import time
from typing import Any

from .._logging import verbose_logging
from .base import BaseOCRPipeline, OCRRequest

_ALLOWED_OCR_TYPES = frozenset({"latex", "code", "table", "figure"})


class BaseMultimodalLLMOCRPipeline(BaseOCRPipeline):
    """Shared OCR flow for multimodal LLM providers."""

    provider_name = "LLM"

    def __init__(
        self,
        *,
        model: str,
        verbose: bool = False,
        allow_remote_image_urls: bool = False,
    ) -> None:
        """Store and validate the model name used by the pipeline.

        Args:
            model: Provider model name to use for OCR.
            verbose: Whether to emit debug logs to stderr during OCR.
            allow_remote_image_urls: Whether provider OCR may fetch and upload
                public remote image URLs.

        Returns:
            ``None``. The pipeline stores the normalized model string.
        """
        normalized_model = model.strip()
        if not normalized_model:
            raise ValueError(f"model is required for {self.__class__.__name__}")
        self.model = normalized_model
        self._verbose = verbose
        self._allow_remote_image_urls = allow_remote_image_urls
        self._logger = logging.getLogger(self.__class__.__module__)

    def __call__(self, request: OCRRequest) -> dict[str, str]:
        """Run OCR against one image using a multimodal LLM backend.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A validated ``{"type", "payload"}`` OCR result mapping.
        """
        with verbose_logging(self._verbose):
            total_started = time.monotonic()
            self._debug(
                "starting OCR request "
                f"(model={self.model}, source={self._describe_request_source(request)})"
            )
            response = self._create_response(request)
            parse_started = time.monotonic()
            self._debug("parsing structured OCR response")
            result = self._parse_response(response)
            self._debug(
                "completed OCR request "
                f"in {self._format_duration(time.monotonic() - total_started)} "
                f"(parse={self._format_duration(time.monotonic() - parse_started)}, "
                f"type={result['type']}, payload_chars={len(result['payload'])})"
            )
            return result

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

    def _ensure_remote_image_urls_allowed(self, request: OCRRequest) -> None:
        if not self._allow_remote_image_urls and self._is_remote_http_source(
            request.src.strip()
        ):
            self._logger.warning(
                "%s OCR blocked remote image URL while allow_remote_image_urls is disabled "
                "(source=%s)",
                self.provider_name,
                self._describe_request_source(request),
            )
            raise ValueError(
                f"Remote HTTP(S) image URLs are disabled by default for "
                f"{self.provider_name} OCR; pass allow_remote_image_urls=True "
                f"(or use --allow-remote-image-urls in the CLI) to opt in."
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

    def _debug(self, message: str) -> None:
        """Emit a verbose OCR debug line when verbose logging is enabled.

        Args:
            message: Human-readable debug message to print.

        Returns:
            ``None``. The message is written to stderr when verbose mode is active.
        """
        self._logger.debug("%s OCR: %s", self.provider_name, message)

    def _describe_request_source(self, request: OCRRequest) -> str:
        """Summarize the OCR input image for debug output.

        Args:
            request: OCR metadata and image source information.

        Returns:
            A short source summary suitable for logs.
        """
        src = request.src.strip()
        if not src:
            return "empty"
        if src.startswith("data:"):
            return "data-uri"

        resolved_path = self.resolve_image_path(request)
        if resolved_path is not None:
            return str(resolved_path)
        return self._truncate_debug_value(src)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format a duration for human-readable debug output.

        Args:
            seconds: Elapsed time in seconds.

        Returns:
            A compact duration string.
        """
        return f"{seconds:.2f}s"

    @staticmethod
    def _truncate_debug_value(value: str, *, limit: int = 120) -> str:
        """Trim long debug strings so logs stay readable.

        Args:
            value: Raw debug text.
            limit: Maximum number of characters to keep.

        Returns:
            A normalized and truncated string.
        """
        normalized = " ".join(value.split())
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[: limit - 3]}..."


__all__ = [
    "BaseMultimodalLLMOCRPipeline",
    "OCRRequest",
]
