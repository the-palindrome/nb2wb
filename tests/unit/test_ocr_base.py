from __future__ import annotations

import pytest

from nb2wb.ocr import base
from nb2wb.ocr.base import BaseOCRPipeline, OCRRequest

_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03"
    b"\x00\x01\x8e\xea\xfe\x0e\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _DummyPipeline(BaseOCRPipeline):
    def __call__(self, request: OCRRequest) -> dict[str, str]:
        return {"type": "figure", "payload": ""}


class _FakeHeaders:
    def __init__(self, *, content_type: str, content_length: int | None = None) -> None:
        self._content_type = content_type
        self._values: dict[str, str] = {}
        if content_length is not None:
            self._values["Content-Length"] = str(content_length)

    def get(self, name: str, default: str | None = None) -> str | None:
        return self._values.get(name, default)

    def get_content_type(self) -> str:
        return self._content_type


class _FakeResponse:
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
        self.headers = _FakeHeaders(
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


class _FakeOpener:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def open(self, request, timeout: int):
        self.calls.append({"url": request.full_url, "timeout": timeout})
        return self._response


class TestBaseOcrPipelineRemoteSources:
    def test_read_image_bytes_supports_remote_http_sources(self, monkeypatch):
        pipeline = _DummyPipeline()
        response = _FakeResponse(
            data=_TINY_PNG,
            content_type="image/png",
            url="https://example.com/img.png",
            content_length=len(_TINY_PNG),
        )
        opener = _FakeOpener(response)

        monkeypatch.setattr(base, "_is_private_host", lambda host: False)
        monkeypatch.setattr(
            base.urllib.request,
            "build_opener",
            lambda *args: opener,
        )

        image_bytes, mime_type = pipeline.read_image_bytes(
            OCRRequest(src="https://example.com/img.png")
        )

        assert image_bytes == _TINY_PNG
        assert mime_type == "image/png"
        assert opener.calls == [
            {
                "url": "https://example.com/img.png",
                "timeout": base._REMOTE_IMAGE_TIMEOUT,
            }
        ]

    def test_load_image_supports_remote_http_sources(self, monkeypatch):
        pipeline = _DummyPipeline()
        response = _FakeResponse(
            data=_TINY_PNG,
            content_type="image/png",
            url="https://example.com/figure.png",
        )
        opener = _FakeOpener(response)

        monkeypatch.setattr(base, "_is_private_host", lambda host: False)
        monkeypatch.setattr(
            base.urllib.request,
            "build_opener",
            lambda *args: opener,
        )

        image = pipeline.load_image(OCRRequest(src="https://example.com/figure.png"))

        assert image.size == (1, 1)
        assert image.mode == "RGB"

    def test_read_image_bytes_rejects_private_remote_hosts(self):
        pipeline = _DummyPipeline()

        with pytest.raises(ValueError, match="private/loopback"):
            pipeline.read_image_bytes(OCRRequest(src="http://127.0.0.1/secret.png"))

    def test_read_image_bytes_accepts_mislabeled_remote_images(self, monkeypatch):
        pipeline = _DummyPipeline()
        response = _FakeResponse(
            data=_TINY_PNG,
            content_type="application/octet-stream",
            url="https://example.com/mislabeled",
        )
        opener = _FakeOpener(response)

        monkeypatch.setattr(base, "_is_private_host", lambda host: False)
        monkeypatch.setattr(
            base.urllib.request,
            "build_opener",
            lambda *args: opener,
        )

        image_bytes, mime_type = pipeline.read_image_bytes(
            OCRRequest(src="https://example.com/mislabeled")
        )

        assert mime_type == "image/png"
        assert image_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    def test_read_image_bytes_rejects_non_image_remote_payloads(self, monkeypatch):
        pipeline = _DummyPipeline()
        response = _FakeResponse(
            data=b"<html>not an image</html>",
            content_type="text/html",
            url="https://example.com/not-image",
        )
        opener = _FakeOpener(response)

        monkeypatch.setattr(base, "_is_private_host", lambda host: False)
        monkeypatch.setattr(
            base.urllib.request,
            "build_opener",
            lambda *args: opener,
        )

        with pytest.raises(ValueError, match="Disallowed MIME type"):
            pipeline.read_image_bytes(OCRRequest(src="https://example.com/not-image"))
