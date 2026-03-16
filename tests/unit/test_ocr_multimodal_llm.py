from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from nb2wb.ocr.base import OCRRequest
from nb2wb.ocr.openai import OpenAIOCRPipeline


_DATA_URL = "data:image/png;base64,QUJD"


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
