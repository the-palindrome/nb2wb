"""Unit tests for HTML-table to image rendering."""
from __future__ import annotations

import base64
import io

from PIL import Image

from nb2wb.config import TableConfig
from nb2wb.renderers.table_renderer import render_table_html, render_tables_as_images


def _decode_data_uri(uri: str) -> bytes:
    assert uri.startswith("data:image/png;base64,")
    payload = uri.split(",", 1)[1]
    return base64.b64decode(payload)


class TestTableRenderer:
    def test_render_table_html_returns_png_data_uri(self):
        table_html = (
            "<table><thead><tr><th>A</th><th>B</th></tr></thead>"
            "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>"
        )
        config = TableConfig(mode="image", image_width=600, font_size=24)

        uri = render_table_html(table_html, config)
        png_bytes = _decode_data_uri(uri)

        assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        image = Image.open(io.BytesIO(png_bytes))
        assert image.width == 600
        assert image.height > 0

    def test_render_tables_as_images_replaces_table_tags(self):
        html = (
            "<p>Before</p>"
            "<table><tr><th>H</th></tr><tr><td>Cell</td></tr></table>"
            "<p>After</p>"
        )
        config = TableConfig(mode="image", image_width=500, font_size=22)

        result = render_tables_as_images(html, config)

        assert "<table" not in result.lower()
        assert 'alt="table"' in result
        assert "<p>Before</p>" in result
        assert "<p>After</p>" in result

    def test_render_tables_as_images_leaves_non_table_html_untouched(self):
        html = "<p>No tables here</p>"
        config = TableConfig(mode="image")

        result = render_tables_as_images(html, config)

        assert result == html
