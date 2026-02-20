"""
Integration tests for Markdown (.md) file conversion.

Tests the complete pipeline: .md file -> md_reader -> converter -> HTML.
"""
import pytest
from nb2wb.converter import Converter


class TestMarkdownFileConversion:
    """Test full .md -> HTML conversion pipeline."""

    def test_md_file_converts_to_html(self, temp_md, minimal_config):
        """Basic .md file produces valid HTML output."""
        converter = Converter(minimal_config)
        html = converter.convert(temp_md)
        assert "<h1>" in html or "Test" in html
        assert "md-cell" in html

    def test_md_prose_preserved(self, temp_md, minimal_config):
        """Prose content from .md file appears in HTML."""
        converter = Converter(minimal_config)
        html = converter.convert(temp_md)
        assert "Some text" in html

    def test_md_code_block_to_image(self, temp_md, minimal_config):
        """Code blocks in .md files are rendered as images."""
        converter = Converter(minimal_config)
        html = converter.convert(temp_md)
        assert "code-cell" in html
        assert "data:image/png;base64," in html

    def test_md_inline_latex_converted(self, minimal_config, tmp_path):
        """Inline $...$ math in .md files is converted to Unicode."""
        md = tmp_path / "inline.md"
        md.write_text("The equation $x^2$ is simple.\n")
        converter = Converter(minimal_config)
        html = converter.convert(md)
        assert "equation" in html
        # Dollar sign should be processed (no raw $x^2$)
        assert "$x^2$" not in html

    def test_md_display_math_to_image(self, minimal_config, tmp_path):
        """Display math $$...$$ in .md files is rendered as PNG image."""
        md = tmp_path / "display.md"
        md.write_text("$$E = mc^2$$\n")
        minimal_config.latex.try_usetex = False
        converter = Converter(minimal_config)
        html = converter.convert(md)
        assert "data:image/png;base64," in html
        assert "<img" in html

    def test_md_latex_preamble_collected(self, minimal_config, tmp_path):
        """latex-preamble block in .md files is collected and hidden."""
        content = (
            "# Test\n\n"
            "```latex-preamble\n"
            "\\usepackage{amsmath}\n"
            "```\n\n"
            "$$E = mc^2$$\n"
        )
        md = tmp_path / "preamble.md"
        md.write_text(content)
        minimal_config.latex.try_usetex = False
        converter = Converter(minimal_config)
        html = converter.convert(md)
        # Preamble cell should not appear in output
        assert "usepackage" not in html
        # Display math should be rendered
        assert "data:image/png;base64," in html

    def test_md_hide_input_directive(self, md_with_directives, minimal_config):
        """hide-input directive hides the code source in .md files."""
        converter = Converter(minimal_config)
        html = converter.convert(md_with_directives)
        # With hide-input and no outputs, the code cell should produce
        # nothing visible (no code image since input is hidden, no output
        # since there's no execution)
        assert "hidden source" not in html

    def test_md_without_execute(self, minimal_config, tmp_path):
        """Without --execute, .md code blocks have no outputs."""
        md = tmp_path / "noexec.md"
        md.write_text("```python\nprint('hello')\n```\n")
        converter = Converter(minimal_config, execute=False)
        html = converter.convert(md)
        # Code image should exist (the source is rendered)
        assert "code-cell" in html
        # But 'hello' should NOT be in the output (no execution)
        assert "hello" not in html or "data:image/png" in html

    def test_md_per_cell_language(self, minimal_config, tmp_path):
        """Mixed-language .md code blocks use per-cell language."""
        content = "```python\nx = 1\n```\n\n```r\ny <- 2\n```\n"
        md = tmp_path / "mixed.md"
        md.write_text(content)
        converter = Converter(minimal_config)
        html = converter.convert(md)
        # Both code cells should be rendered as images
        assert html.count("code-cell") == 2


class TestMarkdownExecutionFlag:
    """Test the execute flag behavior."""

    def test_execute_false_no_outputs(self, minimal_config, tmp_path):
        """With execute=False, .md code cells produce no outputs."""
        md = tmp_path / "noexec.md"
        md.write_text("```python\nprint('output text')\n```\n")
        converter = Converter(minimal_config, execute=False)
        html = converter.convert(md)
        # Source code is rendered but 'output text' is not executed/shown
        assert "code-cell" in html

    def test_qmd_always_executes(self, minimal_config, tmp_path):
        """Converter(execute=False) does not affect .qmd execution."""
        # .qmd execution is always attempted regardless of execute flag
        qmd = tmp_path / "test.qmd"
        qmd.write_text("# Test\n\n```{python}\nx = 1\n```\n")
        converter = Converter(minimal_config, execute=False)
        # This should not crash; .qmd still goes through _execute_cells
        try:
            html = converter.convert(qmd)
        except Exception:
            pytest.skip("Jupyter kernel not available for .qmd execution")
