"""Unit tests for parser-based HTML/SVG sanitizer."""
from __future__ import annotations

from nb2wb.sanitizer import sanitize_fragment


class TestSanitizeFragmentHtml:
    def test_drops_script_and_event_handlers(self):
        html = '<div onclick="evil()">ok</div><script>alert(1)</script>'
        out = sanitize_fragment(html, profile="html").lower()
        assert "<script" not in out
        assert "onclick=" not in out
        assert ">ok<" in out

    def test_blocks_javascript_urls(self):
        html = '<a href="javascript:alert(1)">x</a>'
        out = sanitize_fragment(html, profile="html").lower()
        assert "javascript:" not in out
        assert "<a" in out

    def test_handles_slash_prefixed_attrs(self):
        html = '<img/onerror=alert(1) src="x.png">'
        out = sanitize_fragment(html, profile="html").lower()
        assert "onerror=" not in out
        assert "<img" in out

    def test_blocks_remote_css_urls(self):
        html = '<style>body{background-image:url("https://evil.test/x.png")}</style>'
        out = sanitize_fragment(html, profile="html").lower()
        assert "https://evil.test" not in out
        assert "url()" in out

    def test_allows_data_image_css_urls(self):
        data_url = "data:image/png;base64,aaaa"
        html = f'<div style="background-image:url({data_url})"></div>'
        out = sanitize_fragment(html, profile="html").lower()
        assert data_url in out

    def test_allows_fragment_css_urls(self):
        html = '<svg><style>.x{fill:url(#grad)}</style></svg>'
        out = sanitize_fragment(html, profile="svg").lower()
        assert "url(#grad)" in out


class TestSanitizeFragmentSvg:
    def test_svg_blocks_event_handler_and_keeps_shape(self):
        svg = '<svg/onload=alert(1)><rect width="5" height="5"/></svg>'
        out = sanitize_fragment(svg, profile="svg").lower()
        assert "onload=" not in out
        assert "<rect" in out
