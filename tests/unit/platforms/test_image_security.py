"""
Security tests for image handling in platform builders.

Tests protection against SSRF, path traversal, MIME type confusion,
and oversized downloads.
"""
from __future__ import annotations

import base64
import http.server
import threading
import urllib.request
from pathlib import Path
from unittest.mock import patch

import pytest

from nb2wb.platforms.base import (
    PlatformBuilder,
    _SafeRedirectHandler,
    _is_private_host,
    _MAX_IMAGE_BYTES,
)
from nb2wb.platforms.substack import SubstackBuilder
from nb2wb.platforms.medium import MediumBuilder
from nb2wb.platforms.x import XArticlesBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal valid 1x1 white PNG
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03"
    b"\x00\x01\x8e\xea\xfe\x0e\x00\x00\x00\x00IEND\xaeB`\x82"
)

_TINY_PNG_B64 = base64.b64encode(_TINY_PNG).decode()


def _make_html_with_img(src: str) -> str:
    return f'<img src="{src}" alt="test">'


# ---------------------------------------------------------------------------
# _is_private_host
# ---------------------------------------------------------------------------


class TestIsPrivateHost:
    def test_localhost_ip(self):
        assert _is_private_host("127.0.0.1") is True

    def test_private_10_range(self):
        assert _is_private_host("10.0.0.1") is True

    def test_private_172_range(self):
        assert _is_private_host("172.16.0.1") is True

    def test_private_192_range(self):
        assert _is_private_host("192.168.1.1") is True

    def test_cgnat_range(self):
        assert _is_private_host("100.64.0.1") is True

    def test_multicast_range(self):
        assert _is_private_host("224.0.0.1") is True

    def test_public_ip(self):
        assert _is_private_host("8.8.8.8") is False

    def test_ipv6_loopback(self):
        assert _is_private_host("::1") is True

    def test_localhost_hostname(self):
        assert _is_private_host("localhost") is True

    def test_unresolvable_hostname_fails_closed(self):
        with patch("socket.getaddrinfo", side_effect=OSError("dns failure")):
            assert _is_private_host("unresolvable.example.test") is True


# ---------------------------------------------------------------------------
# Path traversal
# ---------------------------------------------------------------------------


class TestPathTraversal:
    """Verify that _read_file_as_data_uri blocks traversal attacks."""

    def test_rejects_absolute_path(self):
        with pytest.raises(ValueError, match="Absolute image path"):
            PlatformBuilder._read_file_as_data_uri("/etc/passwd")

    def test_rejects_dotdot_traversal(self):
        with pytest.raises(ValueError, match="Path traversal"):
            PlatformBuilder._read_file_as_data_uri("../../../etc/passwd")

    def test_rejects_dotdot_in_middle(self):
        with pytest.raises(ValueError, match="Path traversal"):
            PlatformBuilder._read_file_as_data_uri("images/../../../etc/passwd")

    def test_allows_simple_relative_path(self, tmp_path, monkeypatch):
        """A benign relative path should work when the file exists."""
        monkeypatch.chdir(tmp_path)
        img = tmp_path / "photo.png"
        img.write_bytes(_TINY_PNG)

        result = PlatformBuilder._read_file_as_data_uri("photo.png")
        assert result.startswith("data:image/png;base64,")

    def test_allows_subdirectory_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        subdir = tmp_path / "assets"
        subdir.mkdir()
        img = subdir / "pic.png"
        img.write_bytes(_TINY_PNG)

        result = PlatformBuilder._read_file_as_data_uri("assets/pic.png")
        assert result.startswith("data:image/png;base64,")

    def test_rejects_symlink_escape(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        outside = tmp_path.parent / "outside.png"
        outside.write_bytes(_TINY_PNG)

        link = tmp_path / "link.png"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported in this environment")

        with pytest.raises(ValueError, match="escapes current working directory"):
            PlatformBuilder._read_file_as_data_uri("link.png")


# ---------------------------------------------------------------------------
# SSRF
# ---------------------------------------------------------------------------


class TestSSRF:
    """Verify that _fetch_url_as_data_uri blocks requests to internal hosts."""

    def test_rejects_localhost_url(self):
        with pytest.raises(ValueError, match="private/loopback"):
            PlatformBuilder._fetch_url_as_data_uri("http://127.0.0.1/secret")

    def test_rejects_private_ip_url(self):
        with pytest.raises(ValueError, match="private/loopback"):
            PlatformBuilder._fetch_url_as_data_uri("http://10.0.0.1/admin")

    def test_rejects_localhost_hostname(self):
        with pytest.raises(ValueError, match="private/loopback"):
            PlatformBuilder._fetch_url_as_data_uri("http://localhost:8080/api")

    def test_rejects_169_254_metadata(self):
        with pytest.raises(ValueError, match="private/loopback"):
            PlatformBuilder._fetch_url_as_data_uri(
                "http://169.254.169.254/latest/meta-data/"
            )

    def test_rejects_non_http_scheme(self):
        with pytest.raises(ValueError, match="must use http/https"):
            PlatformBuilder._fetch_url_as_data_uri("ftp://example.com/image.png")

    def test_rejects_multicast_ip_url(self):
        with pytest.raises(ValueError, match="private/loopback"):
            PlatformBuilder._fetch_url_as_data_uri("http://224.0.0.1/stream")

    def test_rejects_url_with_credentials(self):
        with pytest.raises(ValueError, match="must not contain credentials"):
            PlatformBuilder._fetch_url_as_data_uri("https://user:pass@example.com/img.png")

    def test_redirect_handler_rejects_private_target(self):
        handler = _SafeRedirectHandler()
        req = urllib.request.Request("https://example.com/image.png")

        with pytest.raises(ValueError, match="private/loopback"):
            handler.redirect_request(
                req=req,
                fp=None,
                code=302,
                msg="Found",
                headers={},
                newurl="http://127.0.0.1/admin",
            )


# ---------------------------------------------------------------------------
# MIME type validation
# ---------------------------------------------------------------------------


class TestMimeValidation:
    """Verify that non-image MIME types are rejected."""

    def test_rejects_text_html(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "evil.html"
        f.write_text("<script>alert(1)</script>")

        with pytest.raises(ValueError, match="Disallowed MIME type"):
            PlatformBuilder._read_file_as_data_uri("evil.html")

    def test_rejects_application_javascript(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "evil.js"
        f.write_text("alert(1)")

        with pytest.raises(ValueError, match="Disallowed MIME type"):
            PlatformBuilder._read_file_as_data_uri("evil.js")

    def test_accepts_png(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "ok.png"
        f.write_bytes(_TINY_PNG)

        result = PlatformBuilder._read_file_as_data_uri("ok.png")
        assert result.startswith("data:image/png;base64,")

    def test_accepts_jpeg(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Minimal JFIF header
        f = tmp_path / "ok.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        result = PlatformBuilder._read_file_as_data_uri("ok.jpg")
        assert result.startswith("data:image/jpeg;base64,")


# ---------------------------------------------------------------------------
# Size limit
# ---------------------------------------------------------------------------


class TestSizeLimit:
    """Verify that oversized files are rejected."""

    def test_rejects_oversized_local_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        big = tmp_path / "huge.png"
        # Write just over the limit
        big.write_bytes(b"\x89PNG" + b"\x00" * _MAX_IMAGE_BYTES)

        with pytest.raises(ValueError, match="byte limit"):
            PlatformBuilder._read_file_as_data_uri("huge.png")


# ---------------------------------------------------------------------------
# Integration: _to_data_uri fallback behaviour
# ---------------------------------------------------------------------------


class TestToDataUriFallback:
    """_to_data_uri should fail closed on conversion failures."""

    def test_returns_empty_on_traversal(self):
        builder = SubstackBuilder()
        result = builder._to_data_uri("../../../etc/passwd")
        assert result == ""

    def test_emits_warning_on_conversion_failure(self):
        builder = SubstackBuilder()
        with pytest.warns(RuntimeWarning, match="Could not convert image"):
            result = builder._to_data_uri("../../../etc/passwd")
        assert result == ""

    def test_returns_empty_on_ssrf(self):
        builder = MediumBuilder()
        result = builder._to_data_uri("http://127.0.0.1/secret")
        assert result == ""

    def test_returns_empty_on_bad_mime(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "evil.html").write_text("<script>x</script>")
        builder = XArticlesBuilder()
        result = builder._to_data_uri("evil.html")
        assert result == ""


class TestStrictImageMode:
    """Strict image mode should fail closed for unsafe sources."""

    def test_strict_mode_drops_unresolvable_image_sources(self):
        builder = SubstackBuilder()
        html = '<p><img src="../../../etc/passwd" alt="x"></p>'
        out = builder._embed_images_as_data_uris(html)
        assert "<img" not in out

    def test_strict_mode_keeps_valid_data_uri_images(self):
        builder = MediumBuilder()
        html = f'<img src="data:image/png;base64,{_TINY_PNG_B64}" alt="ok">'
        out = builder._make_images_copyable(html)
        assert "copy-image-btn" in out
        assert "data:image/png;base64" in out


# ---------------------------------------------------------------------------
# CLI _extract_images MIME filtering
# ---------------------------------------------------------------------------


class TestExtractImagesMime:
    """_extract_images should skip non-image MIME types."""

    def test_skips_non_image_mime(self, tmp_path):
        from nb2wb.cli import _extract_images

        # Craft HTML with a data URI using text/html MIME type
        fake_b64 = base64.b64encode(b"<script>alert(1)</script>").decode()
        html = f'<img src="data:text/html;base64,{fake_b64}" />'

        result = _extract_images(html, tmp_path / "images")

        # Should be unchanged — the non-image MIME was skipped
        assert f"data:text/html;base64,{fake_b64}" in result
        # No files should have been written
        images_dir = tmp_path / "images"
        if images_dir.exists():
            assert len(list(images_dir.iterdir())) == 0

    def test_extracts_valid_png(self, tmp_path):
        from nb2wb.cli import _extract_images

        html = f'<img src="data:image/png;base64,{_TINY_PNG_B64}" />'
        result = _extract_images(html, tmp_path / "images")

        assert "images/img_1.png" in result
        assert (tmp_path / "images" / "img_1.png").exists()

    def test_skips_malformed_base64(self, tmp_path):
        from nb2wb.cli import _extract_images

        bad_b64 = "%%%not-base64%%%"
        html = f'<img src="data:image/png;base64,{bad_b64}" />'
        result = _extract_images(html, tmp_path / "images")

        assert f"data:image/png;base64,{bad_b64}" in result
        assert len(list((tmp_path / "images").iterdir())) == 0
