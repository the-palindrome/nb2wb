"""Unit tests for the public Python API (nb2wb.convert)."""
from __future__ import annotations

import nbformat
import nb2wb
import nb2wb.api as api


class TestPublicApi:
    def test_top_level_exports_convert(self):
        assert callable(nb2wb.convert)
        assert callable(nb2wb.supported_targets)

    def test_convert_markdown_with_dict_config(self, tmp_path):
        md = tmp_path / "article.md"
        md.write_text("# Hello API\n\nBody text.")

        html = nb2wb.convert(
            md,
            config={
                "image_width": 900,
                "latex": {"try_usetex": False},
                "safety": {"max_cells": 100},
            },
            target="substack",
            execute=False,
        )

        assert "Hello API" in html
        assert "<html" in html.lower()

    def test_convert_accepts_config_file_path(self, tmp_path):
        md = tmp_path / "article.md"
        md.write_text("# Config Path")
        cfg = tmp_path / "config.yaml"
        cfg.write_text("image_width: 1000\n")

        html = nb2wb.convert(md, config=cfg, target="substack")

        assert "Config Path" in html

    def test_convert_accepts_notebook_payload_dict(self):
        notebook_dict = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": "# Dict Notebook",
                }
            ],
            "metadata": {
                "kernelspec": {"name": "python3", "language": "python"},
                "language_info": {"name": "python"},
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }

        html = nb2wb.convert(
            notebook_dict,
            config={"latex": {"try_usetex": False}},
            target="substack",
            execute=False,
        )

        assert "Dict Notebook" in html
        assert "<html" in html.lower()

    def test_convert_accepts_notebooknode_payload(self):
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_markdown_cell("# NotebookNode Input")]
        nb.metadata = {"kernelspec": {"name": "python3", "language": "python"}}

        html = nb2wb.convert(nb, config={"latex": {"try_usetex": False}})

        assert "NotebookNode Input" in html

    def test_convert_rejects_invalid_notebook_payload(self):
        invalid_payload = {
            "cells": [],
            "metadata": {},
            # Missing nbformat/nbformat_minor
        }

        try:
            nb2wb.convert(invalid_payload)
            raise AssertionError("Expected ValueError for invalid notebook payload")
        except ValueError as exc:
            assert "Invalid Jupyter notebook payload" in str(exc)

    def test_convert_rejects_bad_extension(self, tmp_path):
        txt = tmp_path / "note.txt"
        txt.write_text("hello")

        try:
            nb2wb.convert(txt)
            raise AssertionError("Expected ValueError for unsupported input extension")
        except ValueError as exc:
            assert "must use one of" in str(exc)

    def test_convert_forwards_execute_flag(self, tmp_path, monkeypatch):
        md = tmp_path / "article.md"
        md.write_text("# Execute flag")

        seen: dict[str, object] = {}

        class DummyConverter:
            def __init__(self, config, *, execute):
                seen["execute"] = execute
                seen["config_type"] = type(config).__name__

            def convert(self, notebook_path):
                seen["notebook"] = str(notebook_path)
                return "<div>fragment</div>"

        class DummyBuilder:
            name = "Dummy"

            def build_page(self, content_html: str) -> str:
                return f"<html><body>{content_html}</body></html>"

        monkeypatch.setattr(api, "Converter", DummyConverter)
        monkeypatch.setattr(api, "get_builder", lambda target: DummyBuilder())

        html = api.convert(md, execute=True)

        assert seen["execute"] is True
        assert seen["config_type"] == "Config"
        assert str(md) == seen["notebook"]
        assert "<html>" in html
