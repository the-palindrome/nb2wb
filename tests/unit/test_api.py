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

    def test_supported_targets_include_new_platforms(self):
        assert nb2wb.supported_targets() == [
            "default",
            "substack",
            "medium",
            "x",
            "linkedin",
            "devto",
            "hashnode",
            "ghost",
            "wordpress",
        ]

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

    def test_convert_accepts_notebook_payload_with_cell_ids_from_minor_v4(self):
        notebook_dict = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "id": "c9ab1105",
                    "source": "# Cell IDs on minor v4",
                }
            ],
            "metadata": {
                "kernelspec": {"name": "python3", "language": "python"},
                "language_info": {"name": "python"},
            },
            "nbformat": 4,
            "nbformat_minor": 4,
        }

        html = nb2wb.convert(
            notebook_dict,
            config={"latex": {"try_usetex": False}},
            target="substack",
            execute=False,
        )

        assert "Cell IDs on minor v4" in html
        normalized = api._coerce_notebook_node(notebook_dict)
        assert normalized["nbformat_minor"] >= 5

    def test_convert_accepts_v3_notebook_payload_with_worksheets(self):
        notebook_dict = {
            "nbformat": 3,
            "nbformat_minor": 0,
            "metadata": {"name": "legacy"},
            "worksheets": [
                {
                    "cells": [
                        {
                            "cell_type": "markdown",
                            "metadata": {},
                            "source": "# Legacy V3",
                        }
                    ],
                    "metadata": {},
                }
            ],
        }

        html = nb2wb.convert(
            notebook_dict,
            config={"latex": {"try_usetex": False}},
            target="substack",
            execute=False,
        )

        assert "Legacy V3" in html
        normalized = api._coerce_notebook_node(notebook_dict)
        assert normalized["nbformat"] == 4
        assert normalized["nbformat_minor"] == 5
        assert len(normalized["cells"]) == 1

    def test_convert_accepts_mislabeled_v3_payload_marked_as_v4(self):
        notebook_dict = {
            "nbformat": 4,
            "nbformat_minor": 0,
            "metadata": {"name": "legacy"},
            "worksheets": [
                {
                    "cells": [
                        {
                            "cell_type": "markdown",
                            "metadata": {},
                            "source": "# Mislabeled V3",
                        }
                    ],
                    "metadata": {},
                }
            ],
        }

        html = nb2wb.convert(
            notebook_dict,
            config={"latex": {"try_usetex": False}},
            target="substack",
            execute=False,
        )

        assert "Mislabeled V3" in html
        normalized = api._coerce_notebook_node(notebook_dict)
        assert normalized["nbformat"] == 4
        assert normalized["nbformat_minor"] == 5

    def test_convert_repairs_legacy_v4_code_and_output_fields(self):
        notebook_dict = {
            "nbformat": 4,
            "nbformat_minor": 2,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "code",
                    "metadata": {},
                    "input": "print('hi')",
                    "prompt_number": 7,
                    "outputs": [
                        {
                            "output_type": "stream",
                            "stream": "stdout",
                            "text": "hi\n",
                        },
                        {
                            "output_type": "pyerr",
                            "ename": "ValueError",
                            "evalue": "boom",
                            "traceback": ["Traceback..."],
                        },
                        {
                            "output_type": "pyout",
                            "prompt_number": 7,
                            "metadata": {},
                            "text": "7",
                        },
                    ],
                }
            ],
        }

        html = nb2wb.convert(
            notebook_dict,
            config={"latex": {"try_usetex": False}},
            target="substack",
            execute=False,
        )

        assert "<html" in html.lower()
        normalized = api._coerce_notebook_node(notebook_dict)
        code = normalized["cells"][0]
        assert code["source"] == "print('hi')"
        assert code["execution_count"] == 7
        assert code["outputs"][0]["name"] == "stdout"
        assert code["outputs"][1]["output_type"] == "error"
        assert code["outputs"][2]["output_type"] == "execute_result"
        assert "data" in code["outputs"][2]

    def test_convert_hides_stderr_streams_by_default(self):
        notebook_dict = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "code",
                    "metadata": {"tags": ["hide-input"]},
                    "source": "pass",
                    "execution_count": 1,
                    "outputs": [
                        {
                            "output_type": "stream",
                            "name": "stderr",
                            "text": "warning-like stderr output\n",
                        }
                    ],
                }
            ],
        }

        html = nb2wb.convert(
            notebook_dict,
            config={"latex": {"try_usetex": False}},
            target="substack",
            execute=False,
        )

        assert 'class="code-cell"' not in html

    def test_convert_warnings_mode_renders_stderr_streams(self):
        notebook_dict = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "code",
                    "metadata": {"tags": ["hide-input"]},
                    "source": "pass",
                    "execution_count": 1,
                    "outputs": [
                        {
                            "output_type": "stream",
                            "name": "stderr",
                            "text": "warning-like stderr output\n",
                        }
                    ],
                }
            ],
        }

        html = nb2wb.convert(
            notebook_dict,
            config={"latex": {"try_usetex": False}},
            target="substack",
            execute=False,
            warnings_mode=True,
        )

        assert 'class="code-cell"' in html

    def test_convert_moves_top_level_orig_nbformat_fields_into_metadata(self):
        notebook_dict = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "orig_nbformat": 3,
            "orig_nbformat_minor": 0,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": "# Legacy markers",
                }
            ],
        }

        normalized = api._coerce_notebook_node(notebook_dict)
        assert "orig_nbformat" not in normalized
        assert "orig_nbformat_minor" not in normalized
        assert normalized["metadata"]["orig_nbformat"] == 3
        assert normalized["metadata"]["orig_nbformat_minor"] == 0

    def test_convert_normalizes_duplicate_cell_ids(self):
        notebook_dict = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "id": "dup-id",
                    "source": "# A",
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "id": "dup-id",
                    "source": "# B",
                },
            ],
        }

        normalized = api._coerce_notebook_node(notebook_dict)
        ids = [cell["id"] for cell in normalized["cells"]]
        assert len(ids) == len(set(ids))

    def test_convert_rejects_unsupported_nbformat_major(self):
        notebook_dict = {
            "nbformat": 5,
            "nbformat_minor": 0,
            "metadata": {},
            "cells": [],
        }
        try:
            nb2wb.convert(notebook_dict)
            raise AssertionError("Expected ValueError for unsupported major version")
        except ValueError as exc:
            assert "unsupported major version" in str(exc)

    def test_convert_rejects_unknown_top_level_fields_with_actionable_error(self):
        notebook_dict = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [],
            "unexpected_field": True,
        }
        try:
            nb2wb.convert(notebook_dict)
            raise AssertionError("Expected ValueError for unsupported top-level fields")
        except ValueError as exc:
            assert "unsupported top-level fields" in str(exc)

    def test_convert_accepts_notebooknode_payload(self):
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_markdown_cell("# NotebookNode Input")]
        nb.metadata = {"kernelspec": {"name": "python3", "language": "python"}}

        html = nb2wb.convert(nb, config={"latex": {"try_usetex": False}})

        assert "NotebookNode Input" in html
        assert "Paste into your destination editor." in html
        assert "Substack draft" not in html

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

    def test_convert_raw_mode_omits_toolbar_header(self):
        html = nb2wb.convert(
            "# Raw Output",
            target="substack",
            raw_mode=True,
            config={"latex": {"try_usetex": False}},
        )
        assert 'id="toolbar"' not in html
        assert "Copy to clipboard" not in html
        assert "<script" not in html.lower()
        assert "<head" not in html.lower()

    def test_convert_raw_mode_medium_and_x_use_plain_images_without_copy_containers(self):
        markdown = "![table](data:image/png;base64,abcd)"
        for target in ("medium", "x"):
            html = nb2wb.convert(
                markdown,
                target=target,
                raw_mode=True,
                config={"latex": {"try_usetex": False}},
            )
            assert "data:image/png;base64,abcd" in html
            assert 'alt="table"' in html
            assert 'class="image-container"' not in html
            assert 'class="copy-image-btn"' not in html
            assert "<script" not in html.lower()
            assert "<head" not in html.lower()

    def test_convert_linkedin_defaults_to_copyable_images(self):
        markdown = "![plot](data:image/png;base64,abcd)"
        html = nb2wb.convert(
            markdown,
            target="linkedin",
            config={"latex": {"try_usetex": False}},
        )
        assert 'class="image-container"' in html
        assert 'class="copy-image-btn"' in html

    def test_convert_dev_targets_default_to_embedded_images(self):
        markdown = "![plot](data:image/png;base64,abcd)"
        for target in ("devto", "hashnode", "ghost", "wordpress"):
            html = nb2wb.convert(
                markdown,
                target=target,
                config={"latex": {"try_usetex": False}},
            )
            assert 'class="image-container"' not in html
            assert 'class="copy-image-btn"' not in html

    def test_convert_target_options_override_image_strategy(self):
        markdown = "![plot](data:image/png;base64,abcd)"
        html = nb2wb.convert(
            markdown,
            target="devto",
            target_options={"image_strategy": "copyable"},
            config={"latex": {"try_usetex": False}},
        )
        assert 'class="image-container"' in html
        assert 'class="copy-image-btn"' in html
        assert "async function copyImage" in html
        assert 'querySelectorAll(".image-container")' in html

    def test_convert_copyable_images_upgrade_simple_script_mode(self):
        markdown = "![plot](data:image/png;base64,abcd)"
        html = nb2wb.convert(
            markdown,
            target="substack",
            target_options={"image_strategy": "copyable"},
            config={"latex": {"try_usetex": False}},
        )
        assert 'class="image-container"' in html
        assert "async function copyImage" in html
        assert "container.replaceWith(img)" in html

    def test_convert_copyable_images_keep_toolbar_hidden_when_copy_script_disabled(self):
        markdown = "![plot](data:image/png;base64,abcd)"
        html = nb2wb.convert(
            markdown,
            target="default",
            target_options={
                "image_strategy": "copyable",
                "copy_script_mode": "none",
            },
            config={"latex": {"try_usetex": False}},
        )
        assert 'class="image-container"' in html
        assert "async function copyImage" in html
        assert 'id="copy-btn"' not in html

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

    def test_convert_treats_path_like_string_as_content(self):
        html = nb2wb.convert("missing_article.md")
        assert "missing_article.md" in html

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
            def __init__(self, config, *, execute, warnings_mode):
                seen["execute"] = execute
                seen["warnings_mode"] = warnings_mode
                seen["config_type"] = type(config).__name__

            def convert_notebook(self, notebook, *, cwd):
                seen["notebook_type"] = type(notebook).__name__
                seen["cwd"] = str(cwd)
                return "<div>fragment</div>"

        class DummyBuilder:
            name = "Dummy"

            def build_page(self, content_html: str, *, raw_mode: bool = False) -> str:
                seen["raw_mode"] = raw_mode
                return f"<html><body>{content_html}</body></html>"

        monkeypatch.setattr(api, "Converter", DummyConverter)
        monkeypatch.setattr(
            api,
            "get_builder",
            lambda target, target_options=None: DummyBuilder(),
        )

        html = api.convert("# Execute flag", execute=True, raw_mode=True)

        assert seen["execute"] is True
        assert seen["warnings_mode"] is False
        assert seen["config_type"] == "Config"
        assert seen["notebook_type"] == "NotebookNode"
        assert seen["cwd"]
        assert seen["raw_mode"] is True
        assert "<html>" in html
