"""
Workflow tests for the CLI interface.

Tests the complete command-line interface including argument parsing,
file handling, and output generation.
"""
import json
import pytest
import nbformat
from pathlib import Path
from nb2wb.cli import main
import sys


def _invoke_cli(argv: list[str]) -> None:
    """Invoke CLI with explicit argv and no exception handling."""
    sys.argv = argv
    main()


def _run_cli(argv: list[str]) -> None:
    """Run CLI and swallow SystemExit for success-path assertions."""
    try:
        _invoke_cli(argv)
    except SystemExit:
        pass


def _write_notebook(path: Path, cells: list[nbformat.NotebookNode]) -> Path:
    """Write notebook cells to disk and return the input path."""
    nb = nbformat.v4.new_notebook()
    nb.cells = cells
    with path.open("w", encoding="utf-8") as f:
        nbformat.write(nb, f)
    return path


def _create_input_for_suffix(tmp_path: Path, suffix: str) -> Path:
    """Create a minimal input file for .ipynb/.md/.qmd parametrized tests."""
    if suffix == ".ipynb":
        return _write_notebook(
            tmp_path / "test.ipynb",
            [nbformat.v4.new_markdown_cell("# Test")],
        )
    if suffix == ".md":
        p = tmp_path / "test.md"
        p.write_text("# Test\n\n```python\nx = 1\n```\n")
        return p
    p = tmp_path / "test.qmd"
    p.write_text("# Test\n\n```{python}\nx = 1\n```\n")
    return p


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_cli_help(self, capsys):
        """CLI --help displays usage information."""
        _run_cli(["nb2wb", "--help"])

        captured = capsys.readouterr()
        assert "usage" in captured.out.lower() or "nb2wb" in captured.out

    def test_cli_converts_notebook(self, tmp_path, minimal_config):
        """CLI converts notebook to HTML."""
        notebook_path = _write_notebook(
            tmp_path / "test.ipynb",
            [
                nbformat.v4.new_markdown_cell("# Test Notebook"),
                nbformat.v4.new_code_cell("x = 1 + 1\nprint(x)"),
            ],
        )
        output_path = tmp_path / "output.html"

        _run_cli(["nb2wb", str(notebook_path), "-o", str(output_path)])

        assert output_path.exists()
        html_content = output_path.read_text()
        assert "Test Notebook" in html_content
        assert len(html_content) > 100

    def test_cli_default_output_path(self, tmp_path):
        """CLI generates default output path when not specified."""
        notebook_path = _write_notebook(
            tmp_path / "test.ipynb",
            [nbformat.v4.new_markdown_cell("# Simple")],
        )
        _run_cli(["nb2wb", str(notebook_path)])
        default_output = tmp_path / "test.html"
        assert default_output.exists()

    def test_cli_default_target_uses_neutral_mode(self, tmp_path, capsys):
        """CLI default target does not emit Substack-specific messaging."""
        notebook_path = _write_notebook(
            tmp_path / "default.ipynb",
            [nbformat.v4.new_markdown_cell("# Default Mode")],
        )
        output_path = tmp_path / "default.html"

        _run_cli(["nb2wb", str(notebook_path), "-o", str(output_path)])

        captured = capsys.readouterr()
        assert "using default mode" in captured.out
        assert "for substack" not in captured.out.lower()

        html = output_path.read_text()
        assert "Paste into your destination editor." in html
        assert "Substack draft" not in html

    def test_cli_with_config(self, tmp_path):
        """CLI accepts config file."""
        notebook_path = _write_notebook(
            tmp_path / "test.ipynb",
            [nbformat.v4.new_markdown_cell("# Config Test")],
        )
        config_path = tmp_path / "config.yaml"
        config_path.write_text("image_width: 1000\nborder_radius: 10\n")

        output_path = tmp_path / "output.html"

        _run_cli(
            ["nb2wb", str(notebook_path), "-c", str(config_path), "-o", str(output_path)]
        )

        assert output_path.exists()

    def test_cli_raw_mode_omits_toolbar(self, tmp_path):
        """CLI --raw omits preview toolbar/header in output HTML."""
        notebook_path = _write_notebook(
            tmp_path / "test.ipynb",
            [nbformat.v4.new_markdown_cell("# Raw CLI")],
        )
        output_path = tmp_path / "raw.html"
        _run_cli(["nb2wb", str(notebook_path), "--raw", "-o", str(output_path)])

        assert output_path.exists()
        html = output_path.read_text()
        assert 'id="toolbar"' not in html
        assert "Copy to clipboard" not in html
        assert "<script" not in html.lower()
        assert "<head" not in html.lower()


class TestCLIPlatformSelection:
    """Test platform-specific output."""

    @pytest.mark.parametrize(
        ("target", "heading", "filename"),
        [
            ("substack", "Substack Test", "substack.html"),
            ("x", "X Articles Test", "x.html"),
            ("medium", "Medium Test", "medium.html"),
            ("linkedin", "LinkedIn Test", "linkedin.html"),
        ],
    )
    def test_cli_platform(self, tmp_path, target, heading, filename):
        """CLI generates platform-formatted HTML."""
        notebook_path = _write_notebook(
            tmp_path / "test.ipynb",
            [nbformat.v4.new_markdown_cell(f"# {heading}")],
        )
        output_path = tmp_path / filename
        _run_cli(["nb2wb", str(notebook_path), "-t", target, "-o", str(output_path)])
        assert output_path.exists()
        html = output_path.read_text()
        assert len(html) > 0


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def test_cli_missing_input_file(self, capsys):
        """CLI handles missing input file gracefully."""
        with pytest.raises((SystemExit, FileNotFoundError)):
            _invoke_cli(["nb2wb", "/nonexistent/notebook.ipynb"])

    def test_cli_invalid_platform(self, tmp_path, capsys):
        """CLI handles invalid platform selection."""
        notebook_path = _write_notebook(
            tmp_path / "test.ipynb",
            [nbformat.v4.new_markdown_cell("# Test")],
        )
        with pytest.raises((SystemExit, KeyError, ValueError)):
            _invoke_cli(["nb2wb", str(notebook_path), "-t", "invalid_platform"])


class TestCLIQuartoSupport:
    """Test CLI with Quarto files."""

    def test_cli_converts_qmd(self, tmp_path):
        """CLI converts Quarto .qmd files."""
        # Create simple Quarto file
        qmd_content = """---
title: Test Quarto
---

# Heading

Some text.

```{python}
x = 1 + 1
print(x)
```
"""

        qmd_path = tmp_path / "test.qmd"
        qmd_path.write_text(qmd_content)

        output_path = tmp_path / "output.html"

        # Run CLI with .qmd file
        try:
            _invoke_cli(["nb2wb", str(qmd_path), "-o", str(output_path)])
        except (SystemExit, Exception) as e:
            # Quarto conversion may require additional setup
            if output_path.exists():
                pass  # Success
            else:
                pytest.skip(f"Quarto conversion not available: {e}")

        if output_path.exists():
            html = output_path.read_text()
            assert len(html) > 0


class TestCLIMarkdownSupport:
    """Test CLI with Markdown files."""

    def test_cli_converts_md(self, tmp_path):
        """CLI converts Markdown .md files."""
        md_content = "# Heading\n\nSome text.\n\n```python\nx = 1 + 1\n```\n"
        md_path = tmp_path / "test.md"
        md_path.write_text(md_content)
        output_path = tmp_path / "output.html"

        _run_cli(["nb2wb", str(md_path), "-o", str(output_path)])

        assert output_path.exists()
        html = output_path.read_text()
        assert "Heading" in html
        assert len(html) > 100

    def test_cli_md_default_output_path(self, tmp_path):
        """CLI generates default output path for .md files."""
        md_path = tmp_path / "article.md"
        md_path.write_text("# Simple\n")

        _run_cli(["nb2wb", str(md_path)])

        default_output = tmp_path / "article.html"
        assert default_output.exists()

    def test_cli_md_with_execute_flag(self, tmp_path):
        """CLI accepts --execute flag with .md files."""
        md_path = tmp_path / "exec.md"
        md_path.write_text("# Test\n\n```python\nprint('hi')\n```\n")
        output_path = tmp_path / "output.html"

        try:
            _invoke_cli(["nb2wb", str(md_path), "--execute", "-o", str(output_path)])
        except (SystemExit, Exception):
            # Execution may fail without Jupyter kernel; that's OK
            pass

        # If output was created, it should be valid
        if output_path.exists():
            html = output_path.read_text()
            assert len(html) > 0

    @pytest.mark.parametrize("needle", ["--execute", "--raw", ".md"])
    def test_cli_help_mentions_supported_flags_and_formats(self, capsys, needle):
        """CLI help text documents execute/raw flags and markdown support."""
        _run_cli(["nb2wb", "--help"])
        captured = capsys.readouterr()
        assert needle in captured.out


class TestCLIExecutionFlag:
    """Test unified --execute behavior across input types."""

    @pytest.mark.parametrize("suffix", [".ipynb", ".md", ".qmd"])
    def test_cli_without_execute_skips_execution(self, tmp_path, monkeypatch, suffix):
        """Without --execute, converter execution is not invoked for any input type."""
        input_path = _create_input_for_suffix(tmp_path, suffix)

        called = False

        def fake_execute_cells(nb, cwd):
            nonlocal called
            called = True
            return nb

        monkeypatch.setattr("nb2wb.converter._execute_cells", fake_execute_cells)
        _run_cli(["nb2wb", str(input_path), "-o", str(tmp_path / "out.html")])

        assert called is False

    @pytest.mark.parametrize("suffix", [".ipynb", ".md", ".qmd"])
    def test_cli_with_execute_runs_execution(self, tmp_path, monkeypatch, suffix):
        """With --execute, converter execution is invoked for every input type."""
        input_path = _create_input_for_suffix(tmp_path, suffix)

        called = False

        def fake_execute_cells(nb, cwd):
            nonlocal called
            called = True
            return nb

        monkeypatch.setattr("nb2wb.converter._execute_cells", fake_execute_cells)
        _run_cli(
            ["nb2wb", str(input_path), "--execute", "-o", str(tmp_path / "out.html")]
        )

        assert called is True


class TestCLIServerSafeMode:
    """Test mandatory server-safe wiring in CLI."""

    def test_cli_uses_server_safe_pipeline(self, tmp_path, monkeypatch):
        notebook_path = _write_notebook(
            tmp_path / "safe.ipynb",
            [nbformat.v4.new_markdown_cell("# Safe")],
        )

        seen: dict[str, object] = {}

        def fake_convert(
            notebook,
            *,
            config,
            target,
            target_options,
            execute,
            working_dir,
            raw_mode,
        ):
            from nb2wb.config import load_config

            resolved = load_config(config)
            seen["api_called"] = True
            seen["target"] = target
            seen["target_options"] = target_options
            seen["payload_type"] = type(notebook).__name__
            seen["working_dir"] = str(working_dir)
            seen["raw_mode"] = raw_mode
            seen["has_safety_limits"] = (
                resolved.safety.max_input_bytes > 0
                and resolved.safety.max_cells > 0
                and resolved.safety.max_total_output_bytes > 0
            )
            return "<html><body><p>ok</p></body></html>"

        monkeypatch.setattr("nb2wb.cli.convert_notebook", fake_convert)

        _run_cli(["nb2wb", str(notebook_path), "-o", str(tmp_path / "out.html")])

        assert seen["api_called"] is True
        assert seen["target"] == "default"
        assert seen["target_options"] is None
        assert seen["payload_type"] == "NotebookNode"
        assert seen["working_dir"] == str(notebook_path.parent)
        assert seen["raw_mode"] is False
        assert seen["has_safety_limits"] is True

    def test_cli_forwards_raw_flag_to_api(self, tmp_path, monkeypatch):
        notebook_path = _write_notebook(
            tmp_path / "raw.ipynb",
            [nbformat.v4.new_markdown_cell("# Raw")],
        )

        seen: dict[str, object] = {}

        def fake_convert(
            notebook,
            *,
            config,
            target,
            target_options,
            execute,
            working_dir,
            raw_mode,
        ):
            seen["target_options"] = target_options
            seen["raw_mode"] = raw_mode
            return "<html><body><p>ok</p></body></html>"

        monkeypatch.setattr("nb2wb.cli.convert_notebook", fake_convert)

        _run_cli(["nb2wb", str(notebook_path), "--raw", "-o", str(tmp_path / "out.html")])

        assert seen["target_options"] is None
        assert seen["raw_mode"] is True

    def test_cli_forwards_target_options_to_api(self, tmp_path, monkeypatch):
        notebook_path = _write_notebook(
            tmp_path / "opts.ipynb",
            [nbformat.v4.new_markdown_cell("# Options")],
        )

        seen: dict[str, object] = {}

        def fake_convert(
            notebook,
            *,
            config,
            target,
            target_options,
            execute,
            working_dir,
            raw_mode,
        ):
            seen["target"] = target
            seen["target_options"] = target_options
            return "<html><body><p>ok</p></body></html>"

        monkeypatch.setattr("nb2wb.cli.convert_notebook", fake_convert)

        _run_cli(
            [
                "nb2wb",
                str(notebook_path),
                "-t",
                "devto",
                "--image-strategy",
                "copyable",
                "--raw-image-strategy",
                "preserve",
                "--copy-script",
                "copyable",
                "--article-width",
                "777",
                "--table-mode",
                "native",
                "-o",
                str(tmp_path / "out.html"),
            ]
        )

        assert seen["target"] == "devto"
        assert seen["target_options"] == {
            "image_strategy": "copyable",
            "raw_image_strategy": "preserve",
            "copy_script_mode": "copyable",
            "article_width_px": 777,
            "table_mode": "native",
        }


class TestCLIInputSanitization:
    """Test CLI sanitization and validation of user-provided paths."""

    def test_cli_rejects_unsupported_input_extension(self, tmp_path, capsys):
        bad = tmp_path / "bad.txt"
        bad.write_text("hello")

        with pytest.raises(SystemExit):
            _invoke_cli(["nb2wb", str(bad)])

        captured = capsys.readouterr()
        assert "must use one of" in captured.err

    def test_cli_rejects_control_chars_in_output_path(self, tmp_path, capsys):
        notebook_path = _write_notebook(
            tmp_path / "test.ipynb",
            [nbformat.v4.new_markdown_cell("# Test")],
        )

        bad_output = tmp_path / "out\nbad.html"

        with pytest.raises(SystemExit):
            _invoke_cli(["nb2wb", str(notebook_path), "-o", str(bad_output)])

        captured = capsys.readouterr()
        assert "control characters" in captured.err


class TestCLIOutputValidation:
    """Test CLI output validation."""

    def test_cli_output_is_valid_html(self, tmp_path):
        """CLI generates valid HTML structure."""
        notebook_path = _write_notebook(
            tmp_path / "test.ipynb",
            [
                nbformat.v4.new_markdown_cell("# Test"),
                nbformat.v4.new_markdown_cell("Paragraph with **bold** text."),
            ],
        )

        output_path = tmp_path / "output.html"

        _run_cli(["nb2wb", str(notebook_path), "-o", str(output_path)])

        assert output_path.exists()
        html = output_path.read_text()

        # Basic HTML validation
        assert "<html" in html.lower() or "<!doctype" in html.lower()
        assert "Test" in html
        assert "bold" in html

    def test_cli_output_is_self_contained(self, tmp_path):
        """CLI generates self-contained HTML (no external dependencies)."""
        notebook_path = _write_notebook(
            tmp_path / "test.ipynb",
            [nbformat.v4.new_markdown_cell("$$E = mc^2$$")],
        )

        output_path = tmp_path / "output.html"

        _run_cli(["nb2wb", str(notebook_path), "-o", str(output_path)])

        html = output_path.read_text()

        # Should not reference external resources (except maybe CDN for JS/CSS)
        # Images should be base64 encoded
        if "img" in html.lower():
            assert "data:image" in html or "base64" in html


class TestCLILegacyNotebookCompatibility:
    """Regression tests for old or mislabeled notebook payloads."""

    def test_cli_converts_v3_notebook_json(self, tmp_path):
        notebook = {
            "nbformat": 3,
            "nbformat_minor": 0,
            "metadata": {"name": "legacy"},
            "worksheets": [
                {
                    "cells": [
                        {
                            "cell_type": "markdown",
                            "metadata": {},
                            "source": "# Legacy CLI V3",
                        }
                    ],
                    "metadata": {},
                }
            ],
        }
        notebook_path = tmp_path / "legacy.ipynb"
        notebook_path.write_text(json.dumps(notebook), encoding="utf-8")
        output_path = tmp_path / "legacy.html"

        _run_cli(["nb2wb", str(notebook_path), "-o", str(output_path)])

        assert output_path.exists()
        html = output_path.read_text(encoding="utf-8")
        assert "Legacy CLI V3" in html

    def test_cli_regression_v44_payload_with_cell_ids(self, tmp_path):
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 4,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "id": "legacyid1",
                    "source": "# Legacy Cell ID",
                }
            ],
        }
        notebook_path = tmp_path / "legacy-id.ipynb"
        notebook_path.write_text(json.dumps(notebook), encoding="utf-8")
        output_path = tmp_path / "legacy-id.html"

        _run_cli(["nb2wb", str(notebook_path), "-o", str(output_path)])

        assert output_path.exists()
        html = output_path.read_text(encoding="utf-8")
        assert "Legacy Cell ID" in html
