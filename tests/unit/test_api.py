"""Unit tests for the public Python API (nb2wb.convert)."""
from __future__ import annotations

import nbformat
import nb2wb
import nb2wb.api as api


class TestPublicApi:
    def test_top_level_exports_convert(self):
        assert callable(nb2wb.convert)
        assert callable(nb2wb.load_input_payload)
        assert callable(nb2wb.load_markdown_payload)
        assert callable(nb2wb.load_quarto_payload)
        assert callable(nb2wb.load_notebook_payload)
        assert callable(nb2wb.supported_targets)

    def test_convert_markdown_with_dict_config(self):
        html = nb2wb.convert(
            "# Hello API\n\nBody text.",
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
        cfg = tmp_path / "config.yaml"
        cfg.write_text("image_width: 1000\n")

        html = nb2wb.convert("# Config Path", config=cfg, target="substack")

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

    def test_convert_accepts_in_memory_markdown_string(self):
        markdown_text = "# In-memory MD\n\nBody from payload."

        html = nb2wb.convert(
            markdown_text,
            config={"latex": {"try_usetex": False}},
            target="substack",
            execute=False,
        )

        assert "In-memory MD" in html
        assert "Body from payload" in html
        assert "<html" in html.lower()

    def test_convert_accepts_in_memory_qmd_string(self):
        qmd_text = (
            "# In-memory QMD\n\n"
            "```{python}\n"
            "x = 1\n"
            "print(x)\n"
            "```\n"
        )

        html = nb2wb.convert(
            qmd_text,
            config={"latex": {"try_usetex": False}},
            target="substack",
            execute=False,
        )

        assert "In-memory QMD" in html
        assert "<html" in html.lower()

    def test_convert_accepts_in_memory_markdown_payload_mapping(self):
        payload = {
            "format": "md",
            "content": "# Mapping MD\n\nBody text.",
        }

        html = nb2wb.convert(
            payload,
            config={"latex": {"try_usetex": False}},
            target="substack",
            execute=False,
        )

        assert "Mapping MD" in html
        assert "Body text." in html

    def test_convert_accepts_in_memory_qmd_payload_mapping(self):
        payload = {
            "format": "qmd",
            "content": "# Mapping QMD\n\n```{python}\nprint('ok')\n```\n",
        }

        html = nb2wb.convert(payload, config={"latex": {"try_usetex": False}})

        assert "Mapping QMD" in html

    def test_convert_accepts_markdown_alias_and_source_field(self):
        payload = {
            "format": "markdown",
            "source": "# Alias format\n\nWorks.",
        }

        html = nb2wb.convert(payload, config={"latex": {"try_usetex": False}})

        assert "Alias format" in html

    def test_convert_rejects_in_memory_text_payload_with_invalid_format(self):
        payload = {"format": "txt", "content": "# nope"}

        try:
            nb2wb.convert(payload)
            raise AssertionError("Expected TypeError for invalid in-memory text format")
        except TypeError as exc:
            assert "format" in str(exc)

    def test_convert_rejects_in_memory_text_payload_without_content(self):
        payload = {"format": "md"}

        try:
            nb2wb.convert(payload)
            raise AssertionError("Expected TypeError for missing in-memory text content")
        except TypeError as exc:
            assert "content" in str(exc)

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

    def test_convert_rejects_path_objects(self, tmp_path):
        md = tmp_path / "article.md"
        md.write_text("# Path Input")
        try:
            nb2wb.convert(md)
            raise AssertionError("Expected TypeError for path input")
        except TypeError as exc:
            assert "load_input_payload" in str(exc)

    def test_convert_rejects_path_like_string(self):
        try:
            nb2wb.convert("missing_article.md")
            raise AssertionError("Expected TypeError for path-like string input")
        except TypeError as exc:
            assert "load_input_payload" in str(exc)

    def test_load_input_payload_reads_markdown_file(self, tmp_path):
        md = tmp_path / "article.md"
        md.write_text("# Loaded Markdown\n\nBody text.")

        payload = nb2wb.load_input_payload(md)

        assert payload == {
            "format": "md",
            "content": "# Loaded Markdown\n\nBody text.",
        }

        html = nb2wb.convert(payload)
        assert "Loaded Markdown" in html

    def test_load_input_payload_reads_quarto_file(self, tmp_path):
        qmd = tmp_path / "article.qmd"
        qmd.write_text("# Loaded QMD\n\n```{python}\nprint('ok')\n```\n")

        payload = nb2wb.load_input_payload(qmd)

        assert payload == {
            "format": "qmd",
            "content": "# Loaded QMD\n\n```{python}\nprint('ok')\n```\n",
        }

        html = nb2wb.convert(payload)
        assert "Loaded QMD" in html

    def test_load_input_payload_reads_ipynb_file(self, tmp_path):
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_markdown_cell("# Loaded IPYNB")]
        nb.metadata = {"kernelspec": {"name": "python3", "language": "python"}}
        ipynb = tmp_path / "article.ipynb"
        with ipynb.open("w", encoding="utf-8") as handle:
            nbformat.write(nb, handle)

        payload = nb2wb.load_input_payload(ipynb)
        assert isinstance(payload, nbformat.NotebookNode)

        html = nb2wb.convert(payload)
        assert "Loaded IPYNB" in html

    def test_load_markdown_payload_rejects_wrong_extension(self, tmp_path):
        qmd = tmp_path / "article.qmd"
        qmd.write_text("# QMD")
        try:
            nb2wb.load_markdown_payload(qmd)
            raise AssertionError("Expected ValueError for extension mismatch")
        except ValueError as exc:
            assert ".md" in str(exc)

    def test_load_input_payload_rejects_unsupported_extension(self, tmp_path):
        txt = tmp_path / "note.txt"
        txt.write_text("hello")
        try:
            nb2wb.load_input_payload(txt)
            raise AssertionError("Expected ValueError for unsupported extension")
        except ValueError as exc:
            assert "must use one of" in str(exc)

    def test_load_input_payload_rejects_missing_file(self):
        try:
            nb2wb.load_input_payload("missing_article.md")
            raise AssertionError("Expected FileNotFoundError for missing input path")
        except FileNotFoundError as exc:
            assert "missing_article.md" in str(exc)

    def test_convert_forwards_execute_flag(self, monkeypatch):
        seen: dict[str, object] = {}

        class DummyConverter:
            def __init__(self, config, *, execute):
                seen["execute"] = execute
                seen["config_type"] = type(config).__name__

            def convert_notebook(self, notebook, *, cwd):
                seen["notebook_type"] = type(notebook).__name__
                seen["cwd"] = str(cwd)
                return "<div>fragment</div>"

        class DummyBuilder:
            name = "Dummy"

            def build_page(self, content_html: str) -> str:
                return f"<html><body>{content_html}</body></html>"

        monkeypatch.setattr(api, "Converter", DummyConverter)
        monkeypatch.setattr(api, "get_builder", lambda target: DummyBuilder())

        html = api.convert("# Execute flag", execute=True)

        assert seen["execute"] is True
        assert seen["config_type"] == "Config"
        assert seen["notebook_type"] == "NotebookNode"
        assert seen["cwd"]
        assert "<html>" in html
