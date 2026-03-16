from __future__ import annotations

from pathlib import Path

import pytest

from nb2wb.html_reader import load_html_payload


class TestHtmlReader:
    def test_load_html_payload_reads_html_file(self, tmp_path: Path):
        html_path = tmp_path / "post.html"
        html_path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")

        payload = load_html_payload(html_path)

        assert payload["format"] == "html"
        assert "Hello" in payload["content"]

    def test_load_html_payload_reads_htm_file(self, tmp_path: Path):
        html_path = tmp_path / "post.htm"
        html_path.write_text("<p>Short suffix</p>", encoding="utf-8")

        payload = load_html_payload(html_path)

        assert payload["format"] == "html"
        assert "Short suffix" in payload["content"]

    def test_load_html_payload_rejects_missing_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_html_payload(tmp_path / "missing.html")

    def test_load_html_payload_rejects_bad_suffix(self, tmp_path: Path):
        bad_path = tmp_path / "post.md"
        bad_path.write_text("# nope", encoding="utf-8")

        with pytest.raises(ValueError, match=r"\.htm, \.html|\ .html, \.htm"):
            load_html_payload(bad_path)

    def test_load_html_payload_rejects_control_characters(self, tmp_path: Path):
        bad_path = tmp_path / "bad\nname.html"

        with pytest.raises(ValueError, match="control characters"):
            load_html_payload(bad_path)
