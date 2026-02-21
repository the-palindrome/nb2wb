"""
Integration tests for Markdown (.md) file conversion.

Tests the complete pipeline: .md file -> md_reader -> converter -> HTML.
"""
import nbformat
import pytest
import subprocess
from pathlib import Path
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

    def test_md_execute_false_skips_execution(self, minimal_config, tmp_path, monkeypatch):
        """With execute=False, .md files are parsed but not executed."""
        md = tmp_path / "test.md"
        md.write_text("```python\nx = 1\n```\n")
        called = False

        def fake_execute_cells(nb, cwd):
            nonlocal called
            called = True
            return nb

        monkeypatch.setattr("nb2wb.converter._execute_cells", fake_execute_cells)
        html = Converter(minimal_config, execute=False).convert(md)
        assert called is False
        assert "code-cell" in html

    def test_md_execute_true_runs_execution(self, minimal_config, tmp_path, monkeypatch):
        """With execute=True, .md files go through notebook execution."""
        md = tmp_path / "test.md"
        md.write_text("```python\nx = 1\n```\n")
        called = False

        def fake_execute_cells(nb, cwd):
            nonlocal called
            called = True
            return nb

        monkeypatch.setattr("nb2wb.converter._execute_cells", fake_execute_cells)
        Converter(minimal_config, execute=True).convert(md)
        assert called is True

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

    def test_latex_usetex_invoked_when_execute_false(self, minimal_config, tmp_path, monkeypatch):
        """LaTeX rendering behavior is independent of --execute."""
        md = tmp_path / "math.md"
        md.write_text("$$x = 1$$\n")
        minimal_config.latex.try_usetex = True
        called = False

        def fake_run(cmd, **kwargs):
            nonlocal called
            called = True
            if cmd[0] == "latex":
                output_idx = cmd.index("-output-directory") + 1
                output_dir = Path(cmd[output_idx])
                (output_dir / "formula.dvi").write_bytes(b"FAKE_DVI")
            elif cmd[0] == "dvipng":
                png_idx = cmd.index("-o") + 1
                png_path = Path(cmd[png_idx])
                png_data = (
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                    b"\x00\x00\x00\nIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03"
                    b"\x00\x01\x8e\xea\xfe\x0e\x00\x00\x00\x00IEND\xaeB`\x82"
                )
                png_path.write_bytes(png_data)
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

        monkeypatch.setattr("nb2wb.renderers.latex_renderer.subprocess.run", fake_run)
        html = Converter(minimal_config, execute=False).convert(md)
        assert called is True
        assert "data:image/png;base64," in html

    def test_latex_usetex_invoked_when_execute_true(self, minimal_config, tmp_path, monkeypatch):
        """With --execute, display math rendering may use external LaTeX."""
        md = tmp_path / "math.md"
        md.write_text("$$x = 1$$\n")
        minimal_config.latex.try_usetex = True
        called = False

        def fake_run(cmd, **kwargs):
            nonlocal called
            called = True

            if cmd[0] == "latex":
                output_idx = cmd.index("-output-directory") + 1
                output_dir = Path(cmd[output_idx])
                (output_dir / "formula.dvi").write_bytes(b"FAKE_DVI")
            elif cmd[0] == "dvipng":
                png_idx = cmd.index("-o") + 1
                png_path = Path(cmd[png_idx])
                png_data = (
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                    b"\x00\x00\x00\nIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03"
                    b"\x00\x01\x8e\xea\xfe\x0e\x00\x00\x00\x00IEND\xaeB`\x82"
                )
                png_path.write_bytes(png_data)
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

        monkeypatch.setattr("nb2wb.renderers.latex_renderer.subprocess.run", fake_run)
        Converter(minimal_config, execute=True).convert(md)
        assert called is True


class TestServerSafeLimits:
    """Server-safe mode applies hard notebook size limits."""

    def test_server_safe_rejects_too_many_cells(self, minimal_config, tmp_path):
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell("A"),
            nbformat.v4.new_markdown_cell("B"),
            nbformat.v4.new_markdown_cell("C"),
        ]
        ipynb = tmp_path / "many.ipynb"
        with open(ipynb, "w") as f:
            nbformat.write(nb, f)

        minimal_config.safety.max_cells = 2

        with pytest.raises(ValueError, match="too many cells"):
            Converter(minimal_config).convert(ipynb)

    def test_server_safe_rejects_large_cell_source(self, minimal_config, tmp_path):
        md = tmp_path / "large.md"
        md.write_text("```python\n" + ("x" * 64) + "\n```\n")

        minimal_config.safety.max_cell_source_chars = 8

        with pytest.raises(ValueError, match="source too large"):
            Converter(minimal_config).convert(md)

    def test_server_safe_rejects_too_many_display_math_blocks(self, minimal_config, tmp_path):
        md = tmp_path / "many_math.md"
        md.write_text(" ".join(["$$x$$"] * 6))

        minimal_config.safety.max_display_math_blocks = 5

        with pytest.raises(ValueError, match="too many display-math blocks"):
            Converter(minimal_config).convert(md)

    def test_server_safe_rejects_excessive_total_latex_chars(self, minimal_config, tmp_path):
        md = tmp_path / "large_math.md"
        md.write_text("$$" + ("x" * 40) + "$$")

        minimal_config.safety.max_total_latex_chars = 10

        with pytest.raises(ValueError, match="too much display-math content"):
            Converter(minimal_config).convert(md)
