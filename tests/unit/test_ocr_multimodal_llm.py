from __future__ import annotations

import base64
import json
import logging
import sys
from types import SimpleNamespace

import pytest

from nb2wb.ocr import base as ocr_base
from nb2wb.ocr.base import OCRRequest
from nb2wb.ocr.gemini import GeminiOCRPipeline
from nb2wb.ocr.openai import OpenAIOCRPipeline


_DATA_URL = "data:image/png;base64,QUJD"
_REMOTE_URL = "https://example.com/img.png"
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\r\xefF\xb8"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _FakeResponses:
    def __init__(self, *, result=None, error: Exception | None = None):
        self.calls: list[dict[str, object]] = []
        self._result = result
        self._error = error

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._result


class _FakeClient:
    def __init__(self, *, result=None, error: Exception | None = None):
        self.responses = _FakeResponses(result=result, error=error)


class _FakeGeminiModels:
    def __init__(self, *, result=None, error: Exception | None = None):
        self.calls: list[dict[str, object]] = []
        self._result = result
        self._error = error

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._result


class _FakeGeminiClient:
    def __init__(self, *, result=None, error: Exception | None = None):
        self.models = _FakeGeminiModels(result=result, error=error)


class _FakeRemoteHeaders:
    def __init__(self, *, content_type: str, content_length: int | None = None):
        self._content_type = content_type
        self._values: dict[str, str] = {}
        if content_length is not None:
            self._values["Content-Length"] = str(content_length)

    def get(self, name: str, default: str | None = None) -> str | None:
        return self._values.get(name, default)

    def get_content_type(self) -> str:
        return self._content_type


class _FakeRemoteResponse:
    def __init__(
        self,
        *,
        data: bytes,
        content_type: str,
        url: str,
        content_length: int | None = None,
    ) -> None:
        self._data = data
        self._offset = 0
        self._url = url
        self.headers = _FakeRemoteHeaders(
            content_type=content_type,
            content_length=content_length,
        )
        self.fp = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def geturl(self) -> str:
        return self._url

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk = self._data[self._offset :]
            self._offset = len(self._data)
            return chunk
        if self._offset >= len(self._data):
            return b""
        end = min(self._offset + size, len(self._data))
        chunk = self._data[self._offset : end]
        self._offset = end
        return chunk


class _FakeRemoteOpener:
    def __init__(self, response: _FakeRemoteResponse):
        self._response = response
        self.calls: list[dict[str, object]] = []

    def open(self, request, timeout: int):
        self.calls.append({"url": request.full_url, "timeout": timeout})
        return self._response


def _patch_remote_fetch(
    monkeypatch,
    *,
    data: bytes = _TINY_PNG,
    content_type: str = "image/png",
    url: str = _REMOTE_URL,
) -> _FakeRemoteOpener:
    response = _FakeRemoteResponse(
        data=data,
        content_type=content_type,
        url=url,
        content_length=len(data),
    )
    opener = _FakeRemoteOpener(response)
    monkeypatch.setattr(ocr_base, "_is_private_host", lambda host: False)
    monkeypatch.setattr(
        ocr_base.urllib.request,
        "build_opener",
        lambda *args: opener,
    )
    return opener


class TestOpenAIOcrPipeline:
    def test_requires_api_key_without_client(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        try:
            OpenAIOCRPipeline(model="gpt-4.1-mini")
        except ValueError as exc:
            assert "OPENAI_API_KEY" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected missing API key to raise ValueError")

    def test_resolves_api_key_from_environment(self, monkeypatch):
        fake_module = SimpleNamespace(OpenAI=lambda api_key: {"api_key": api_key})
        monkeypatch.setitem(sys.modules, "openai", fake_module)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-env")

        pipeline = OpenAIOCRPipeline(model="gpt-4.1-mini")

        assert pipeline._client == {"api_key": "sk-test-env"}

    def test_builds_responses_request_with_image_and_schema(self):
        fake_client = _FakeClient(
            result=SimpleNamespace(output_text='{"type":"figure","payload":""}')
        )
        pipeline = OpenAIOCRPipeline(model="gpt-4.1-mini", client=fake_client)

        result = pipeline(OCRRequest(src=_DATA_URL, alt="Chart"))

        assert result == {"type": "figure", "payload": ""}
        call = fake_client.responses.calls[0]
        assert call["model"] == "gpt-4.1-mini"
        assert "type" in call["text"]["format"]["schema"]["properties"]
        content = call["input"][0]["content"][0]
        assert content["type"] == "input_image"
        assert content["image_url"] == _DATA_URL
        assert "structured JSON" in call["instructions"]

    def test_builds_responses_request_with_remote_image_url(self, monkeypatch):
        fake_client = _FakeClient(
            result=SimpleNamespace(output_text='{"type":"figure","payload":""}')
        )
        pipeline = OpenAIOCRPipeline(model="gpt-4.1-mini", client=fake_client)
        opener = _patch_remote_fetch(monkeypatch)

        result = pipeline(OCRRequest(src=_REMOTE_URL, alt="Remote chart"))

        assert result == {"type": "figure", "payload": ""}
        assert opener.calls[0]["url"] == _REMOTE_URL
        assert 0 < opener.calls[0]["timeout"] <= ocr_base._REMOTE_IMAGE_TIMEOUT
        call = fake_client.responses.calls[0]
        content = call["input"][0]["content"][0]
        assert content["type"] == "input_image"
        assert content["image_url"].startswith("data:image/png;base64,")

    def test_parses_all_supported_types(self):
        for result_type, payload in (
            ("latex", r"\alpha + \beta"),
            ("code", "print(42)"),
            ("table", "|A|B|\n|-|-|\n|1|2|"),
            ("figure", ""),
        ):
            fake_client = _FakeClient(
                result=SimpleNamespace(
                    output_text=json.dumps({"type": result_type, "payload": payload})
                )
            )
            pipeline = OpenAIOCRPipeline(model="gpt-4.1-mini", client=fake_client)
            parsed = pipeline(OCRRequest(src=_DATA_URL))
            assert parsed == {"type": result_type, "payload": payload}

    def test_raises_on_refusal_response(self):
        fake_client = _FakeClient(
            result=SimpleNamespace(
                output=[
                    SimpleNamespace(
                        type="message",
                        content=[SimpleNamespace(type="refusal", refusal="cannot help")],
                    )
                ]
            )
        )
        pipeline = OpenAIOCRPipeline(model="gpt-4.1-mini", client=fake_client)

        try:
            pipeline(OCRRequest(src=_DATA_URL))
        except RuntimeError as exc:
            assert "refused" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected refusal to raise RuntimeError")

    def test_raises_on_malformed_json_response(self):
        fake_client = _FakeClient(result=SimpleNamespace(output_text="not-json"))
        pipeline = OpenAIOCRPipeline(model="gpt-4.1-mini", client=fake_client)

        try:
            pipeline(OCRRequest(src=_DATA_URL))
        except RuntimeError as exc:
            assert "invalid JSON" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected malformed JSON to raise RuntimeError")

    def test_raises_on_invalid_schema_response(self):
        fake_client = _FakeClient(
            result=SimpleNamespace(output_text='{"type":"bogus","payload":""}')
        )
        pipeline = OpenAIOCRPipeline(model="gpt-4.1-mini", client=fake_client)

        try:
            pipeline(OCRRequest(src=_DATA_URL))
        except RuntimeError as exc:
            assert "must be one of" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected invalid schema to raise RuntimeError")

    def test_sanitizes_api_key_from_client_error_message(self):
        fake_client = _FakeClient(error=RuntimeError("bad key sk-secret-value"))
        pipeline = OpenAIOCRPipeline(model="gpt-4.1-mini", client=fake_client)

        try:
            pipeline(OCRRequest(src=_DATA_URL))
        except RuntimeError as exc:
            message = str(exc)
            assert "sk-secret-value" not in message
            assert "[REDACTED]" in message
        else:  # pragma: no cover
            raise AssertionError("expected client error to raise RuntimeError")


class TestGeminiOcrPipeline:
    def test_requires_api_key_without_client(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        try:
            GeminiOCRPipeline(model="gemini-2.0-flash")
        except ValueError as exc:
            message = str(exc)
            assert "GEMINI_API_KEY" in message
            assert "GOOGLE_API_KEY" in message
        else:  # pragma: no cover
            raise AssertionError("expected missing API key to raise ValueError")

    def test_resolves_api_key_from_environment(self, monkeypatch):
        fake_genai = SimpleNamespace(Client=lambda api_key: {"api_key": api_key})
        fake_module = SimpleNamespace(genai=fake_genai)
        monkeypatch.setitem(sys.modules, "google", fake_module)
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyA12345678901234567890123456789012")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        pipeline = GeminiOCRPipeline(model="gemini-2.0-flash")

        assert pipeline._client == {
            "api_key": "AIzaSyA12345678901234567890123456789012"
        }

    def test_builds_generate_content_request_with_image_and_schema(self):
        fake_client = _FakeGeminiClient(
            result=SimpleNamespace(text='{"type":"figure","payload":""}')
        )
        pipeline = GeminiOCRPipeline(model="gemini-2.0-flash", client=fake_client)

        result = pipeline(OCRRequest(src=_DATA_URL, alt="Chart"))

        assert result == {"type": "figure", "payload": ""}
        call = fake_client.models.calls[0]
        assert call["model"] == "gemini-2.0-flash"
        assert "type" in call["config"]["response_schema"]["properties"]
        assert "additionalProperties" not in call["config"]["response_schema"]
        parts = call["contents"][0]["parts"]
        assert "structured JSON" in parts[0]["text"]
        assert parts[1]["inline_data"]["mime_type"] == "image/png"
        assert parts[1]["inline_data"]["data"] == "QUJD"

    def test_builds_generate_content_request_with_remote_image_url(self, monkeypatch):
        fake_client = _FakeGeminiClient(
            result=SimpleNamespace(text='{"type":"figure","payload":""}')
        )
        pipeline = GeminiOCRPipeline(model="gemini-2.0-flash", client=fake_client)
        opener = _patch_remote_fetch(monkeypatch)

        result = pipeline(OCRRequest(src=_REMOTE_URL, alt="Remote chart"))

        assert result == {"type": "figure", "payload": ""}
        assert opener.calls[0]["url"] == _REMOTE_URL
        assert 0 < opener.calls[0]["timeout"] <= ocr_base._REMOTE_IMAGE_TIMEOUT
        call = fake_client.models.calls[0]
        inline_data = call["contents"][0]["parts"][1]["inline_data"]
        assert inline_data["mime_type"] == "image/png"
        assert inline_data["data"] == base64.b64encode(_TINY_PNG).decode("ascii")

    def test_parses_all_supported_types(self):
        for result_type, payload in (
            ("latex", r"\alpha + \beta"),
            ("code", "print(42)"),
            ("table", "|A|B|\n|-|-|\n|1|2|"),
            ("figure", ""),
        ):
            fake_client = _FakeGeminiClient(
                result=SimpleNamespace(
                    text=json.dumps({"type": result_type, "payload": payload})
                )
            )
            pipeline = GeminiOCRPipeline(model="gemini-2.0-flash", client=fake_client)
            parsed = pipeline(OCRRequest(src=_DATA_URL))
            assert parsed == {"type": result_type, "payload": payload}

    def test_raises_on_refusal_response(self):
        fake_client = _FakeGeminiClient(
            result=SimpleNamespace(
                prompt_feedback=SimpleNamespace(
                    block_reason="SAFETY",
                    block_reason_message="blocked",
                )
            )
        )
        pipeline = GeminiOCRPipeline(model="gemini-2.0-flash", client=fake_client)

        try:
            pipeline(OCRRequest(src=_DATA_URL))
        except RuntimeError as exc:
            assert "refused" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected refusal to raise RuntimeError")

    def test_raises_on_malformed_json_response(self):
        fake_client = _FakeGeminiClient(result=SimpleNamespace(text="not-json"))
        pipeline = GeminiOCRPipeline(model="gemini-2.0-flash", client=fake_client)

        try:
            pipeline(OCRRequest(src=_DATA_URL))
        except RuntimeError as exc:
            assert "invalid JSON" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected malformed JSON to raise RuntimeError")

    def test_raises_on_invalid_schema_response(self):
        fake_client = _FakeGeminiClient(
            result=SimpleNamespace(text='{"type":"bogus","payload":""}')
        )
        pipeline = GeminiOCRPipeline(model="gemini-2.0-flash", client=fake_client)

        try:
            pipeline(OCRRequest(src=_DATA_URL))
        except RuntimeError as exc:
            assert "must be one of" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected invalid schema to raise RuntimeError")

    def test_sanitizes_api_key_from_client_error_message(self):
        fake_client = _FakeGeminiClient(
            error=RuntimeError(
                "bad key AIzaSyA12345678901234567890123456789012"
            )
        )
        pipeline = GeminiOCRPipeline(model="gemini-2.0-flash", client=fake_client)

        try:
            pipeline(OCRRequest(src=_DATA_URL))
        except RuntimeError as exc:
            message = str(exc)
            assert "AIzaSyA12345678901234567890123456789012" not in message
            assert "[REDACTED]" in message
        else:  # pragma: no cover
            raise AssertionError("expected client error to raise RuntimeError")

    def test_emits_verbose_logs(self, caplog):
        caplog.set_level(logging.DEBUG, logger="nb2wb")
        fake_client = _FakeGeminiClient(
            result=SimpleNamespace(text='{"type":"figure","payload":""}')
        )
        pipeline = GeminiOCRPipeline(
            model="gemini-2.0-flash",
            client=fake_client,
            verbose=True,
        )

        result = pipeline(OCRRequest(src=_DATA_URL, alt="Chart"))

        assert result == {"type": "figure", "payload": ""}
        assert "Gemini OCR: starting OCR request" in caplog.text
        assert "Gemini OCR: reading image bytes" in caplog.text
        assert "Gemini OCR: calling models.generate_content" in caplog.text
        assert "Gemini OCR: completed OCR request" in caplog.text
