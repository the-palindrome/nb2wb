"""
Integration tests for markdown cell processing in the converter.

Tests the complete pipeline: markdown → LaTeX processing → HTML conversion.
"""
import pytest
import nbformat
from nb2wb.converter import Converter
from nb2wb.config import Config, LatexConfig


class TestMarkdownCellProcessing:
    """Test markdown cell conversion pipeline."""

    def test_plain_markdown_to_html(self, minimal_config, tmp_path):
        """Plain markdown converts to HTML."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell("# Heading\n\nParagraph text.")
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = converter.convert(notebook_path)

        assert "<h1>Heading</h1>" in html
        assert "Paragraph text" in html

    def test_inline_latex_converted(self, minimal_config, tmp_path):
        """Inline LaTeX converted to Unicode."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell("The equation $x^2 + y^2 = r^2$ describes a circle.")
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = converter.convert(notebook_path)

        # Inline math should be converted
        assert "$" not in html or "data:image" in html  # Either no $ or it's in base64
        assert "describes a circle" in html

    def test_display_math_to_image(self, minimal_config, tmp_path):
        """Display math converted to image."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell("$$E = mc^2$$")
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        minimal_config.latex.try_usetex = False  # Use mathtext
        converter = Converter(minimal_config)
        html = converter.convert(notebook_path)

        # Should contain image tag with base64 data
        assert "<img" in html
        assert "data:image/png;base64," in html

    def test_mixed_inline_and_display_math(self, minimal_config, tmp_path):
        """Mixed inline and display math handled correctly."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(
                "Consider the equation $x = 1$ and its expansion:\n\n"
                "$$x^2 + 2x + 1 = 0$$"
            )
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        minimal_config.latex.try_usetex = False
        converter = Converter(minimal_config)
        html = converter.convert(notebook_path)

        assert "Consider the equation" in html
        assert "<img" in html  # Display math
        assert "data:image/png;base64," in html

    def test_fenced_code_blocks_protected(self, minimal_config, tmp_path):
        """Fenced code blocks not processed as LaTeX."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(
                "Here's some code:\n\n```python\nx = $1  # This $ should not be processed\n```"
            )
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = converter.convert(notebook_path)

        # Code block should be preserved
        assert "```" not in html  # Converted to HTML
        assert "<code>" in html or "<pre>" in html
        # Dollar sign content inside code block must be preserved literally
        assert "$1" in html

    def test_multiple_markdown_cells(self, minimal_config, tmp_path):
        """Multiple markdown cells processed in order."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell("# First"),
            nbformat.v4.new_markdown_cell("# Second"),
            nbformat.v4.new_markdown_cell("# Third"),
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = converter.convert(notebook_path)

        # All three headers should appear in order
        first_pos = html.find("First")
        second_pos = html.find("Second")
        third_pos = html.find("Third")

        assert first_pos < second_pos < third_pos

    def test_markdown_extensions_applied(self, minimal_config, tmp_path):
        """Markdown extensions (tables, lists) work correctly."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(
                "| Header 1 | Header 2 |\n"
                "|----------|----------|\n"
                "| Cell 1   | Cell 2   |"
            )
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = converter.convert(notebook_path)

        # Table should be converted to HTML
        assert "<table>" in html or "<th>" in html

    def test_empty_markdown_cell(self, minimal_config, tmp_path):
        """Empty markdown cells handled gracefully."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(""),
            nbformat.v4.new_markdown_cell("# Not Empty"),
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = converter.convert(notebook_path)

        # Should not crash
        assert "Not Empty" in html


class TestEquationReferences:
    """Test equation numbering and cross-references."""

    def test_equation_with_label(self, minimal_config, tmp_path):
        """Equation with \\label gets numbered."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(r"$$x = 1 \label{eq:simple}$$")
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        minimal_config.latex.try_usetex = False
        converter = Converter(minimal_config)
        html = converter.convert(notebook_path)

        # Should contain image (equation rendered)
        assert "data:image/png;base64," in html

    def test_eqref_substitution(self, minimal_config, tmp_path):
        """\\eqref{} replaced with equation number."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(r"$$x = 1 \label{eq:first}$$"),
            nbformat.v4.new_markdown_cell(r"See equation \eqref{eq:first} above."),
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        minimal_config.latex.try_usetex = False
        converter = Converter(minimal_config)
        html = converter.convert(notebook_path)

        # eqref should be replaced with (1)
        assert "(1)" in html
        assert "See equation" in html

    def test_multiple_equations_numbered(self, minimal_config, tmp_path):
        """Multiple equations numbered sequentially."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(r"$$x = 1 \label{eq:one}$$"),
            nbformat.v4.new_markdown_cell(r"$$y = 2 \label{eq:two}$$"),
            nbformat.v4.new_markdown_cell(r"$$z = 3 \label{eq:three}$$"),
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        minimal_config.latex.try_usetex = False
        converter = Converter(minimal_config)
        html = converter.convert(notebook_path)

        # All three equations should be rendered
        assert html.count("data:image/png;base64,") == 3


class TestEdgeCases:
    """Test edge cases in markdown processing."""

    def test_unicode_in_markdown(self, minimal_config, tmp_path):
        """Unicode characters in markdown preserved."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell("Hello 世界 🚀")
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = converter.convert(notebook_path)

        assert "世界" in html or "&#" in html  # Unicode preserved or escaped

    def test_html_in_markdown(self, minimal_config, tmp_path):
        """HTML tags in markdown handled."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell("<strong>Bold</strong> text")
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = converter.convert(notebook_path)

        # HTML should be preserved or escaped safely
        assert "Bold" in html
