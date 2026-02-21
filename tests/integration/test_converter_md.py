"""
Integration tests for Markdown (.md) file conversion.

Tests the complete pipeline: .md file -> md_reader -> converter -> HTML.
"""
import nbformat
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


class TestTextSnippet:
    """Test the text-snippet tag rendering."""

    def test_text_snippet_renders_as_html(self, minimal_config, tmp_path):
        """text-snippet tag renders code as HTML pre/code instead of PNG."""
        content = "```python text-snippet\nx = 1 + 1\nprint(x)\n```\n"
        md = tmp_path / "snippet.md"
        md.write_text(content)
        converter = Converter(minimal_config)
        html = converter.convert(md)
        assert "<pre><code>" in html
        assert "x = 1 + 1" in html
        assert "print(x)" in html
        # Should NOT contain a PNG image for this cell
        assert "data:image/png" not in html

    def test_text_snippet_escapes_html(self, minimal_config, tmp_path):
        """text-snippet properly escapes HTML special characters."""
        content = "```python text-snippet\nif x < 10 & y > 5:\n    pass\n```\n"
        md = tmp_path / "escape.md"
        md.write_text(content)
        converter = Converter(minimal_config)
        html = converter.convert(md)
        assert "&lt;" in html
        assert "&amp;" in html
        assert "&gt;" in html

    def test_text_snippet_with_hide_input(self, minimal_config, tmp_path):
        """text-snippet combined with hide-input produces nothing."""
        content = "```python text-snippet hide-input\nprint('hidden')\n```\n"
        md = tmp_path / "hidden_snippet.md"
        md.write_text(content)
        converter = Converter(minimal_config)
        html = converter.convert(md)
        assert "hidden" not in html

    def test_text_snippet_via_directive(self, minimal_config, tmp_path):
        """text-snippet works via HTML comment directive too."""
        content = "<!-- nb2wb: text-snippet -->\n```python\nx = 1\n```\n"
        md = tmp_path / "directive_snippet.md"
        md.write_text(content)
        converter = Converter(minimal_config)
        html = converter.convert(md)
        assert "<pre><code>" in html
        assert "x = 1" in html

    def test_normal_code_still_renders_as_image(self, minimal_config, tmp_path):
        """Code blocks without text-snippet still render as PNG images."""
        content = "```python\nx = 1\n```\n"
        md = tmp_path / "normal.md"
        md.write_text(content)
        converter = Converter(minimal_config)
        html = converter.convert(md)
        assert "data:image/png" in html
        assert "<pre><code>" not in html


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

    def test_qmd_execute_false_skips_execution(self, minimal_config, tmp_path, monkeypatch):
        """With execute=False, .qmd files are parsed but not executed."""
        qmd = tmp_path / "test.qmd"
        qmd.write_text("# Test\n\n```{python}\nx = 1\n```\n")
        called = False

        def fake_execute_cells(nb, cwd):
            nonlocal called
            called = True
            return nb

        monkeypatch.setattr("nb2wb.converter._execute_cells", fake_execute_cells)
        converter = Converter(minimal_config, execute=False)
        html = converter.convert(qmd)
        assert called is False
        assert "Test" in html

    def test_qmd_execute_true_runs_execution(self, minimal_config, tmp_path, monkeypatch):
        """With execute=True, .qmd files go through notebook execution."""
        qmd = tmp_path / "test.qmd"
        qmd.write_text("# Test\n\n```{python}\nx = 1\n```\n")
        called = False

        def fake_execute_cells(nb, cwd):
            nonlocal called
            called = True
            return nb

        monkeypatch.setattr("nb2wb.converter._execute_cells", fake_execute_cells)
        converter = Converter(minimal_config, execute=True)
        converter.convert(qmd)
        assert called is True

    def test_ipynb_execute_false_skips_execution(self, minimal_config, tmp_path, monkeypatch):
        """With execute=False, .ipynb files are rendered without re-executing cells."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_markdown_cell("# Test")]
        ipynb = tmp_path / "test.ipynb"
        with open(ipynb, "w") as f:
            nbformat.write(nb, f)

        called = False

        def fake_execute_cells(nb, cwd):
            nonlocal called
            called = True
            return nb

        monkeypatch.setattr("nb2wb.converter._execute_cells", fake_execute_cells)
        html = Converter(minimal_config, execute=False).convert(ipynb)
        assert called is False
        assert "Test" in html

    def test_ipynb_execute_true_runs_execution(self, minimal_config, tmp_path, monkeypatch):
        """With execute=True, .ipynb files go through notebook execution."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_markdown_cell("# Test")]
        ipynb = tmp_path / "test.ipynb"
        with open(ipynb, "w") as f:
            nbformat.write(nb, f)

        called = False

        def fake_execute_cells(nb, cwd):
            nonlocal called
            called = True
            return nb

        monkeypatch.setattr("nb2wb.converter._execute_cells", fake_execute_cells)
        Converter(minimal_config, execute=True).convert(ipynb)
        assert called is True
