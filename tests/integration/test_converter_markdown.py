"""
Integration tests for markdown cell processing in the converter.

Tests the complete pipeline: markdown → LaTeX processing → HTML conversion.
"""
import base64
import re

import nbformat
from pathlib import Path
from nb2wb.converter import Converter


def _convert_path(converter: Converter, path: Path) -> str:
    notebook = nbformat.read(path, as_version=4)
    return converter.convert_notebook(notebook, cwd=path.parent)


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
        html = _convert_path(converter, notebook_path)

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
        html = _convert_path(converter, notebook_path)

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
        html = _convert_path(converter, notebook_path)

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
        html = _convert_path(converter, notebook_path)

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
        html = _convert_path(converter, notebook_path)

        # Code block should be preserved
        assert "```" not in html  # Converted to HTML
        assert "<code>" in html or "<pre>" in html
        # Dollar sign content inside code block must be preserved literally
        assert "$1" in html

    def test_tilde_fenced_code_preserves_list_like_lines(self, minimal_config, tmp_path):
        """Tilde-fenced code contents stay verbatim through cuddled-list normalization."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(
                "Here's some code:\n\n~~~python\nparagraph line\n- item\n~~~"
            )
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = _convert_path(converter, notebook_path)

        code_match = re.search(r"<pre><code[^>]*>(.*?)</code></pre>", html, flags=re.DOTALL)
        assert code_match is not None

        code_contents = code_match.group(1)
        assert "paragraph line\n- item" in code_contents
        assert "paragraph line\n\n- item" not in code_contents

    def test_inline_code_protected_from_latex(self, minimal_config, tmp_path):
        """Dollar signs inside backtick code spans are not processed as LaTeX."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(
                "Show `$E = mc^2$` as code."
            )
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = _convert_path(converter, notebook_path)

        # The dollar-sign expression should appear literally inside <code>
        assert "<code>$E = mc^2$</code>" in html
        # No stray HTML-escaped <em> tags from inline LaTeX conversion
        assert "&lt;em&gt;" not in html

    def test_inline_code_with_double_backticks_protected(self, minimal_config, tmp_path):
        """Double-backtick code spans also protected from LaTeX."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(
                "Use ``$\\alpha$`` in your text."
            )
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = _convert_path(converter, notebook_path)

        # The LaTeX inside double backticks should be literal
        assert "<code>" in html
        assert "$\\alpha$" in html or "$" in html
        assert "&lt;em&gt;" not in html

    def test_inline_code_and_inline_math_coexist(self, minimal_config, tmp_path):
        """Inline code and inline math in the same cell both handled correctly."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(
                "Code `$x$` is literal, but $x$ is math."
            )
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = _convert_path(converter, notebook_path)

        # Backtick-protected $x$ should appear literally
        assert "<code>$x$</code>" in html
        # The bare $x$ should be converted (no raw dollar signs outside code)
        # The converted x is wrapped in <em> by the inline math converter
        assert "<em>" in html

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
        html = _convert_path(converter, notebook_path)

        # All three headers should appear in order
        first_pos = html.find("First")
        second_pos = html.find("Second")
        third_pos = html.find("Third")

        assert first_pos < second_pos < third_pos

    def test_markdown_reference_state_does_not_leak_between_cells(self, minimal_config, tmp_path):
        """Reference definitions from one cell must not affect later cells."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(
                "[ref]: https://example.com\n\n[ref]"
            ),
            nbformat.v4.new_markdown_cell("[ref]"),
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = _convert_path(converter, notebook_path)

        # The first cell contains one resolved reference link.
        assert html.count('href="https://example.com"') == 1

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
        html = _convert_path(converter, notebook_path)

        # Table should be converted to HTML
        assert "<table>" in html or "<th>" in html

    def test_markdown_strikethrough_applied(self, minimal_config, tmp_path):
        """GitHub-style ~~strikethrough~~ converts to <del>."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_markdown_cell("~~strikethrough test~~")]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = _convert_path(converter, notebook_path)

        assert "<del>strikethrough test</del>" in html
        assert "~~strikethrough test~~" not in html

    def test_stderr_streams_hidden_by_default(self, minimal_config, tmp_path):
        """Stderr warning/log streams are omitted unless warnings mode is enabled."""
        nb = nbformat.v4.new_notebook()
        cell = nbformat.v4.new_code_cell("pass")
        cell.metadata["tags"] = ["hide-input"]
        cell.outputs = [
            nbformat.v4.new_output(
                output_type="stream",
                name="stderr",
                text="warning-like stderr output\n",
            )
        ]
        nb.cells = [cell]

        notebook_path = tmp_path / "stderr_hidden.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        html = _convert_path(Converter(minimal_config), notebook_path)

        assert 'class="code-cell"' not in html

    def test_stderr_streams_render_when_warnings_mode_enabled(self, minimal_config, tmp_path):
        """Warnings mode restores rendering for stderr stream outputs."""
        nb = nbformat.v4.new_notebook()
        cell = nbformat.v4.new_code_cell("pass")
        cell.metadata["tags"] = ["hide-input"]
        cell.outputs = [
            nbformat.v4.new_output(
                output_type="stream",
                name="stderr",
                text="warning-like stderr output\n",
            )
        ]
        nb.cells = [cell]

        notebook_path = tmp_path / "stderr_visible.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        html = _convert_path(
            Converter(minimal_config, warnings_mode=True),
            notebook_path,
        )

        assert 'class="code-cell"' in html

    def test_markdown_strikethrough_respects_inline_code(self, minimal_config, tmp_path):
        """Backtick code with ~~ stays literal while bare ~~ is rendered."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_markdown_cell("`~~literal~~` and ~~rendered~~")]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = _convert_path(converter, notebook_path)

        assert "<code>~~literal~~</code>" in html
        assert "<del>rendered</del>" in html

    def test_cuddled_unordered_lists_render_as_lists(self, minimal_config, tmp_path):
        """Unordered list markers after text render as a proper list block."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(
                "List intro line\n* first item\n* second item"
            )
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = _convert_path(converter, notebook_path)

        assert "<ul>" in html
        assert "<li>first item</li>" in html
        assert "<li>second item</li>" in html

    def test_cuddled_ordered_lists_render_as_lists(self, minimal_config, tmp_path):
        """Ordered list markers after text render as a proper list block."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(
                "Steps line\n1. first step\n2. second step"
            )
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        converter = Converter(minimal_config)
        html = _convert_path(converter, notebook_path)

        assert "<ol>" in html
        assert "<li>first step</li>" in html
        assert "<li>second step</li>" in html

    def test_markdown_table_can_render_as_image(self, minimal_config, tmp_path):
        """Table HTML can be replaced by a rendered image when configured."""
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(
                "| Name | Value |\n"
                "|:-----|------:|\n"
                "| Foo  |   123 |\n"
                "| Bar  |   456 |"
            )
        ]

        notebook_path = tmp_path / "test.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        minimal_config.table.mode = "image"
        converter = Converter(minimal_config)
        html = _convert_path(converter, notebook_path)

        assert "<table" not in html.lower()
        assert 'alt="table"' in html
        assert "data:image/png;base64," in html

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
        html = _convert_path(converter, notebook_path)

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
        html = _convert_path(converter, notebook_path)

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
        html = _convert_path(converter, notebook_path)

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
        html = _convert_path(converter, notebook_path)

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
        html = _convert_path(converter, notebook_path)

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
        html = _convert_path(converter, notebook_path)

        # HTML should be preserved or escaped safely
        assert "Bold" in html


class TestSecuritySanitization:
    """Test sanitization of notebook-provided HTML/SVG fragments."""

    def test_markdown_script_tags_are_removed(self, minimal_config, tmp_path):
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell(
                '<strong>Safe</strong>'
                '<script>alert(1)</script>'
                '<a href="javascript:alert(1)" onclick="evil()">go</a>'
            )
        ]

        notebook_path = tmp_path / "dangerous_markdown.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        html = _convert_path(Converter(minimal_config), notebook_path)
        lowered = html.lower()
        assert "<script" not in lowered
        assert "onclick=" not in lowered
        assert "javascript:" not in lowered
        assert "Safe" in html
        assert ">go<" in html

    def test_html_output_is_sanitized(self, minimal_config, tmp_path):
        nb = nbformat.v4.new_notebook()
        cell = nbformat.v4.new_code_cell("x = 1")
        cell.outputs = [
            nbformat.from_dict(
                {
                    "output_type": "display_data",
                    "data": {
                        "text/html": (
                            '<div onclick="evil()">OK</div>'
                            '<script>alert(1)</script>'
                            '<a href="javascript:alert(1)">x</a>'
                        )
                    },
                    "metadata": {},
                }
            )
        ]
        nb.cells = [cell]

        notebook_path = tmp_path / "dangerous_output.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        html = _convert_path(Converter(minimal_config), notebook_path)
        lowered = html.lower()
        assert "html-output" in html
        assert "<script" not in lowered
        assert "onclick=" not in lowered
        assert "javascript:" not in lowered
        assert "OK" in html

    def test_svg_output_embeds_sanitized_data_uri(self, minimal_config, tmp_path):
        nb = nbformat.v4.new_notebook()
        cell = nbformat.v4.new_code_cell("x = 1")
        cell.outputs = [
            nbformat.from_dict(
                {
                    "output_type": "display_data",
                    "data": {
                        "image/svg+xml": (
                            '<svg xmlns="http://www.w3.org/2000/svg" onload="evil()">'
                            '<script>alert(1)</script>'
                            '<rect width="10" height="10"/>'
                            "</svg>"
                        )
                    },
                    "metadata": {},
                }
            )
        ]
        nb.cells = [cell]

        notebook_path = tmp_path / "dangerous_svg.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        html = _convert_path(Converter(minimal_config), notebook_path)
        m = re.search(r'data:image/svg\+xml;base64,([^"]+)"', html)
        assert m is not None

        decoded_svg = base64.b64decode(m.group(1)).decode("utf-8")
        lowered = decoded_svg.lower()
        assert "<script" not in lowered
        assert "onload=" not in lowered
        assert "<rect" in lowered

    def test_server_safe_strips_slash_prefixed_event_handlers(self, minimal_config, tmp_path):
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_markdown_cell('<img/onerror=alert(1) src="x.png">')
        ]
        notebook_path = tmp_path / "slash_attrs.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        html = _convert_path(Converter(minimal_config), notebook_path)
        lowered = html.lower()
        assert "onerror=" not in lowered
        assert "<img" in lowered

    def test_server_safe_sanitizes_svg_slash_attr_payload(self, minimal_config, tmp_path):
        nb = nbformat.v4.new_notebook()
        cell = nbformat.v4.new_code_cell("x = 1")
        cell.outputs = [
            nbformat.from_dict(
                {
                    "output_type": "display_data",
                    "data": {"image/svg+xml": '<svg/onload=alert(1)><rect width="1" height="1"/></svg>'},
                    "metadata": {},
                }
            )
        ]
        nb.cells = [cell]
        notebook_path = tmp_path / "slash_svg.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        html = _convert_path(Converter(minimal_config), notebook_path)
        m = re.search(r'data:image/svg\+xml;base64,([^"]+)"', html)
        assert m is not None
        decoded_svg = base64.b64decode(m.group(1)).decode("utf-8").lower()
        assert "onload=" not in decoded_svg
