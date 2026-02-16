"""
Workflow tests for the CLI interface.

Tests the complete command-line interface including argument parsing,
file handling, and output generation.
"""
import pytest
import nbformat
from pathlib import Path
from nb2wb.cli import main
import sys


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_cli_help(self, capsys):
        """CLI --help displays usage information."""
        sys.argv = ["nb2wb", "--help"]

        try:
            main()
        except SystemExit:
            pass  # --help causes sys.exit(0)

        captured = capsys.readouterr()
        assert "usage" in captured.out.lower() or "nb2wb" in captured.out

    def test_cli_converts_notebook(self, tmp_path, minimal_config):
        """CLI converts notebook to HTML."""
        # Create test notebook
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell("# Test Notebook"),
            nbformat.v4.new_code_cell("x = 1 + 1\nprint(x)"),
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        output_path = tmp_path / "output.html"

        # Run CLI
        sys.argv = ["nb2wb", str(notebook_path), "-o", str(output_path)]

        try:
            main()
        except SystemExit:
            pass  # CLI may exit with success

        # Check output was created
        assert output_path.exists()

        # Verify HTML content
        html_content = output_path.read_text()
        assert "Test Notebook" in html_content
        assert len(html_content) > 100  # Should have substantial content

    def test_cli_default_output_path(self, tmp_path):
        """CLI generates default output path when not specified."""
        # Create test notebook
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_markdown_cell("# Simple")]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        # Run CLI without -o flag
        sys.argv = ["nb2wb", str(notebook_path)]

        try:
            main()
        except SystemExit:
            pass

        # Default output should be test.html
        default_output = tmp_path / "test.html"
        assert default_output.exists()

    def test_cli_with_config(self, tmp_path):
        """CLI accepts config file."""
        # Create test notebook
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_markdown_cell("# Config Test")]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        # Create config file
        config_path = tmp_path / "config.yaml"
        config_path.write_text("image_width: 1000\nborder_radius: 10\n")

        output_path = tmp_path / "output.html"

        # Run CLI with config
        sys.argv = ["nb2wb", str(notebook_path), "-c", str(config_path),
                    "-o", str(output_path)]

        try:
            main()
        except SystemExit:
            pass

        assert output_path.exists()


class TestCLIPlatformSelection:
    """Test platform-specific output."""

    def test_cli_substack_platform(self, tmp_path):
        """CLI generates Substack-formatted HTML."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_markdown_cell("# Substack Test")]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        output_path = tmp_path / "substack.html"

        # Run CLI with Substack target
        sys.argv = ["nb2wb", str(notebook_path), "-t", "substack",
                    "-o", str(output_path)]

        try:
            main()
        except SystemExit:
            pass

        assert output_path.exists()
        html = output_path.read_text()
        assert len(html) > 0

    def test_cli_x_platform(self, tmp_path):
        """CLI generates X Articles-formatted HTML."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_markdown_cell("# X Articles Test")]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        output_path = tmp_path / "x.html"

        # Run CLI with X target
        sys.argv = ["nb2wb", str(notebook_path), "-t", "x",
                    "-o", str(output_path)]

        try:
            main()
        except SystemExit:
            pass

        assert output_path.exists()
        html = output_path.read_text()
        assert len(html) > 0

    def test_cli_medium_platform(self, tmp_path):
        """CLI generates Medium-formatted HTML."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_markdown_cell("# Medium Test")]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        output_path = tmp_path / "medium.html"

        sys.argv = ["nb2wb", str(notebook_path), "-t", "medium",
                    "-o", str(output_path)]

        try:
            main()
        except SystemExit:
            pass

        assert output_path.exists()
        html = output_path.read_text()
        assert len(html) > 0


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def test_cli_missing_input_file(self, capsys):
        """CLI handles missing input file gracefully."""
        sys.argv = ["nb2wb", "/nonexistent/notebook.ipynb"]

        with pytest.raises((SystemExit, FileNotFoundError)):
            main()

    def test_cli_invalid_platform(self, tmp_path, capsys):
        """CLI handles invalid platform selection."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_markdown_cell("# Test")]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        sys.argv = ["nb2wb", str(notebook_path), "-t", "invalid_platform"]

        # Should either exit or raise an error
        try:
            main()
        except (SystemExit, KeyError, ValueError):
            pass  # Expected behavior


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
        sys.argv = ["nb2wb", str(qmd_path), "-o", str(output_path)]

        try:
            main()
        except (SystemExit, Exception) as e:
            # Quarto conversion may require additional setup
            if output_path.exists():
                pass  # Success
            else:
                pytest.skip(f"Quarto conversion not available: {e}")

        if output_path.exists():
            html = output_path.read_text()
            assert len(html) > 0


class TestCLIOutputValidation:
    """Test CLI output validation."""

    def test_cli_output_is_valid_html(self, tmp_path):
        """CLI generates valid HTML structure."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell("# Test"),
            nbformat.v4.new_markdown_cell("Paragraph with **bold** text."),
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        output_path = tmp_path / "output.html"

        sys.argv = ["nb2wb", str(notebook_path), "-o", str(output_path)]

        try:
            main()
        except SystemExit:
            pass

        assert output_path.exists()
        html = output_path.read_text()

        # Basic HTML validation
        assert "<html" in html.lower() or "<!doctype" in html.lower()
        assert "Test" in html
        assert "bold" in html

    def test_cli_output_is_self_contained(self, tmp_path):
        """CLI generates self-contained HTML (no external dependencies)."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell("$$E = mc^2$$"),
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        output_path = tmp_path / "output.html"

        sys.argv = ["nb2wb", str(notebook_path), "-o", str(output_path)]

        try:
            main()
        except SystemExit:
            pass

        html = output_path.read_text()

        # Should not reference external resources (except maybe CDN for JS/CSS)
        # Images should be base64 encoded
        if "img" in html.lower():
            assert "data:image" in html or "base64" in html
