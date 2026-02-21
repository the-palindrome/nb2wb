"""
Unit tests for display LaTeX rendering to PNG.

Tests the renderers/latex_renderer.py module which converts display math
($$...$$, \\[...\\], \\begin{equation}...\\end{equation}) to PNG images.
"""
import pytest
import base64
import subprocess
from pathlib import Path
from nb2wb.renderers.latex_renderer import (
    extract_display_math,
    render_latex_block,
    _render_mathtext,
    _color_to_html,
    _color_to_dvipng,
    _trim_and_pad,
    _draw_tag,
    _round_corners,
)
from nb2wb.config import LatexConfig
from PIL import Image
import io


class TestExtractDisplayMath:
    """Test extraction of display math blocks from text."""

    def test_extract_double_dollar(self):
        """Extract $$...$$ blocks."""
        text = "Some text $$E = mc^2$$ more text"
        result = extract_display_math(text)
        assert len(result) == 1
        start, end, latex = result[0]
        assert latex == "E = mc^2"
        assert text[start:end] == "$$E = mc^2$$"

    def test_extract_brackets(self):
        """Extract \\[...\\] blocks."""
        text = r"Some text \[x^2 + y^2 = r^2\] more text"
        result = extract_display_math(text)
        assert len(result) == 1
        start, end, latex = result[0]
        assert latex == "x^2 + y^2 = r^2"

    def test_extract_equation_environment(self):
        """Extract \\begin{equation}...\\end{equation} blocks."""
        text = r"\begin{equation}a + b = c\end{equation}"
        result = extract_display_math(text)
        assert len(result) == 1
        start, end, latex = result[0]
        assert r"\begin{equation}" in latex
        assert r"\end{equation}" in latex

    def test_extract_equation_star(self):
        """Extract \\begin{equation*}...\\end{equation*} blocks."""
        text = r"\begin{equation*}x = 1\end{equation*}"
        result = extract_display_math(text)
        assert len(result) == 1
        start, end, latex = result[0]
        assert r"\begin{equation*}" in latex

    def test_extract_align_environment(self):
        """Extract \\begin{align}...\\end{align} blocks."""
        text = r"\begin{align}x &= 1 \\ y &= 2\end{align}"
        result = extract_display_math(text)
        assert len(result) == 1
        assert r"\begin{align}" in result[0][2]

    def test_extract_multiple_blocks(self):
        """Extract multiple display math blocks."""
        text = "First $$a$$ then $$b$$ and $$c$$"
        result = extract_display_math(text)
        assert len(result) == 3
        assert result[0][2] == "a"
        assert result[1][2] == "b"
        assert result[2][2] == "c"

    def test_extract_sorted_by_position(self):
        """Blocks returned in order of appearance."""
        text = r"First \[x\] then $$y$$ finally \[z\]"
        result = extract_display_math(text)
        assert len(result) == 3
        # Verify sorted by start position
        assert result[0][0] < result[1][0] < result[2][0]

    def test_extract_overlapping_blocks(self):
        """Overlapping blocks handled (first one wins)."""
        # This is a pathological case but should not crash
        text = r"$$a \[ b$$"
        result = extract_display_math(text)
        # Should extract $$a \[$$ and ignore the orphan
        assert len(result) >= 1

    def test_extract_empty_text(self):
        """Empty text returns empty list."""
        result = extract_display_math("")
        assert result == []

    def test_extract_no_math(self):
        """Text with no display math returns empty list."""
        result = extract_display_math("Just plain text here")
        assert result == []

    def test_extract_multiline_math(self):
        """Multiline display math extracted correctly."""
        text = """
Before
$$
x = 1
y = 2
$$
After
"""
        result = extract_display_math(text)
        assert len(result) == 1
        assert "x = 1" in result[0][2]
        assert "y = 2" in result[0][2]


class TestMathTextRendering:
    """Test matplotlib mathtext fallback renderer."""

    def test_render_mathtext_simple(self, minimal_config):
        """Render simple expression with mathtext."""
        latex = "E = mc^2"
        result = _render_mathtext(latex, minimal_config.latex)
        assert result.startswith("data:image/png;base64,")
        # Verify it's valid base64
        b64_data = result.split(",", 1)[1]
        png_bytes = base64.b64decode(b64_data)
        img = Image.open(io.BytesIO(png_bytes))
        assert img.format == "PNG"

    def test_render_mathtext_with_greek(self, minimal_config):
        """Render expression with Greek letters."""
        latex = r"\alpha + \beta = \gamma"
        result = _render_mathtext(latex, minimal_config.latex)
        assert result.startswith("data:image/png;base64,")

    def test_render_mathtext_with_tag(self, minimal_config):
        """Render expression with equation tag."""
        latex = "x = 1"
        result = _render_mathtext(latex, minimal_config.latex, tag=1)
        assert result.startswith("data:image/png;base64,")
        # Tag should be drawn on the image

    def test_render_mathtext_multiline_environment(self, minimal_config):
        """Render multiline environment (converted to single line)."""
        latex = r"\begin{align}x &= 1 \\ y &= 2\end{align}"
        result = _render_mathtext(latex, minimal_config.latex)
        assert result.startswith("data:image/png;base64,")
        # Should handle multiline by joining with \quad

    def test_render_mathtext_custom_color(self):
        """Render with custom color."""
        config = LatexConfig(
            font_size=24,
            dpi=72,
            color="red",
            background="white",
            padding=10,
            image_width=800,
        )
        latex = "x = 1"
        result = _render_mathtext(latex, config)
        assert result.startswith("data:image/png;base64,")


class TestColorConversion:
    """Test color conversion utilities."""

    def test_color_to_html_black(self):
        """Black converts to 000000."""
        result = _color_to_html("black")
        assert result == "000000"

    def test_color_to_html_white(self):
        """White converts to FFFFFF."""
        result = _color_to_html("white")
        assert result == "FFFFFF"

    def test_color_to_html_red(self):
        """Red converts to FF0000."""
        result = _color_to_html("red")
        assert result == "FF0000"

    def test_color_to_html_hex_input(self):
        """Hex color string handled."""
        result = _color_to_html("#8080FF")
        assert len(result) == 6
        # Should be uppercase hex

    def test_color_to_dvipng_black(self):
        """Black converts to dvipng format."""
        result = _color_to_dvipng("black")
        assert result.startswith("rgb")
        assert "0.000000" in result

    def test_color_to_dvipng_white(self):
        """White converts to dvipng format."""
        result = _color_to_dvipng("white")
        assert result.startswith("rgb")
        assert "1.000000" in result

    def test_color_to_dvipng_format(self):
        """dvipng format is 'rgb R G B' with floats."""
        result = _color_to_dvipng("red")
        parts = result.split()
        assert parts[0] == "rgb"
        assert len(parts) == 4
        # Should have three float values
        float(parts[1])
        float(parts[2])
        float(parts[3])


class TestImageProcessing:
    """Test image post-processing functions."""

    def test_trim_and_pad_basic(self, minimal_config):
        """Trim and pad basic image."""
        # Create a small test image
        img = Image.new("RGB", (100, 50), "white")
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle([40, 20, 60, 30], fill="black")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        result = _trim_and_pad(png_bytes, minimal_config.latex)
        result_img = Image.open(io.BytesIO(result))

        # Should be centered on fixed width
        assert result_img.width == minimal_config.latex.image_width

    def test_trim_and_pad_with_tag(self, minimal_config):
        """Trim and pad with equation tag."""
        img = Image.new("RGB", (100, 50), "white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        result = _trim_and_pad(png_bytes, minimal_config.latex, tag=42)
        result_img = Image.open(io.BytesIO(result))

        # Tag should be drawn (can't easily verify text, but image should be valid)
        assert result_img.width == minimal_config.latex.image_width

    def test_draw_tag_on_canvas(self, minimal_config):
        """Draw equation tag on canvas."""
        canvas = Image.new("RGB", (800, 100), "white")
        _draw_tag(canvas, 5, minimal_config.latex)
        # Tag should be drawn (function should not crash)
        # Actual text rendering depends on font availability

    def test_round_corners_basic(self):
        """Apply rounded corners to image."""
        img = Image.new("RGB", (100, 100), "white")
        result = _round_corners(img, 10)

        # Should be RGBA with transparency
        assert result.mode == "RGBA"
        assert result.size == img.size

    def test_round_corners_zero_radius(self):
        """Zero radius should still work."""
        img = Image.new("RGB", (100, 100), "white")
        result = _round_corners(img, 0)
        assert result.mode == "RGBA"


class TestRenderLatexBlock:
    """Test the main render_latex_block function."""

    def test_render_mathtext_fallback(self, minimal_config):
        """Mathtext fallback when try_usetex is False."""
        minimal_config.latex.try_usetex = False
        latex = "x = 1"
        result = render_latex_block(latex, minimal_config.latex)
        assert result.startswith("data:image/png;base64,")

    def test_render_with_preamble(self, minimal_config):
        """Render with custom preamble."""
        minimal_config.latex.try_usetex = False
        latex = "x = 1"
        preamble = r"\usepackage{amsmath}"
        result = render_latex_block(latex, minimal_config.latex, preamble=preamble)
        assert result.startswith("data:image/png;base64,")

    def test_render_with_tag(self, minimal_config):
        """Render with equation tag."""
        minimal_config.latex.try_usetex = False
        latex = "x = 1"
        result = render_latex_block(latex, minimal_config.latex, tag=3)
        assert result.startswith("data:image/png;base64,")

    def test_render_complex_expression(self, minimal_config):
        """Render complex mathematical expression."""
        minimal_config.latex.try_usetex = False
        latex = r"\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}"
        result = render_latex_block(latex, minimal_config.latex)
        assert result.startswith("data:image/png;base64,")

    def test_render_matrix(self, minimal_config):
        """Render matrix expression."""
        minimal_config.latex.try_usetex = False
        latex = r"\begin{bmatrix} 1 & 2 \\ 3 & 4 \end{bmatrix}"
        result = render_latex_block(latex, minimal_config.latex)
        assert result.startswith("data:image/png;base64,")


class TestUseTexRendering:
    """Tests for the usetex rendering path (LaTeX is mocked)."""

    def test_render_usetex_simple(self, minimal_config, mock_latex_available):
        """Render with full LaTeX pipeline (mocked)."""
        minimal_config.latex.try_usetex = True
        latex = "E = mc^2"
        result = render_latex_block(latex, minimal_config.latex)
        assert result.startswith("data:image/png;base64,")

    def test_render_usetex_with_color(self, minimal_config, mock_latex_available):
        """Render with custom colors using usetex (mocked)."""
        minimal_config.latex.try_usetex = True
        minimal_config.latex.color = "red"
        latex = r"x = 1"
        result = render_latex_block(latex, minimal_config.latex)
        assert result.startswith("data:image/png;base64,")

    def test_render_usetex_with_preamble(self, minimal_config, mock_latex_available):
        """Render with custom preamble using usetex (mocked)."""
        minimal_config.latex.try_usetex = True
        latex = r"x = 1"
        preamble = r"\definecolor{customcolor}{RGB}{100,200,50}"
        result = render_latex_block(latex, minimal_config.latex, preamble=preamble)
        assert result.startswith("data:image/png;base64,")

    def test_render_usetex_fallback_on_error(self, minimal_config, mock_latex_unavailable):
        """Falls back to mathtext when LaTeX unavailable."""
        minimal_config.latex.try_usetex = True
        latex = "x = 1"
        # Should fall back to mathtext when LaTeX fails
        result = render_latex_block(latex, minimal_config.latex)
        assert result.startswith("data:image/png;base64,")

    def test_render_usetex_disables_shell_escape(self, minimal_config, monkeypatch):
        """LaTeX subprocess is invoked with shell-escape explicitly disabled."""
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)

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

        monkeypatch.setattr(subprocess, "run", fake_run)
        minimal_config.latex.try_usetex = True
        render_latex_block("x = 1", minimal_config.latex)

        latex_cmd = next(cmd for cmd in calls if cmd[0] == "latex")
        assert "-no-shell-escape" in latex_cmd

    def test_render_usetex_sanitizer_blocks_dangerous_command(self, minimal_config, monkeypatch):
        """Dangerous TeX commands are blocked before launching LaTeX subprocesses."""
        called = False

        def fake_run(cmd, **kwargs):
            nonlocal called
            called = True
            raise RuntimeError("subprocess should not be called for blocked input")

        monkeypatch.setattr(subprocess, "run", fake_run)
        minimal_config.latex.try_usetex = True
        result = render_latex_block("x = 1", minimal_config.latex, preamble=r"\input{secret.tex}")
        assert called is False
        assert result.startswith("data:image/png;base64,")

    def test_render_usetex_sanitizer_blocks_csname_smuggling(self, minimal_config, monkeypatch):
        """Dynamic command construction via \\csname is blocked."""
        called = False

        def fake_run(cmd, **kwargs):
            nonlocal called
            called = True
            raise RuntimeError("subprocess should not be called for blocked input")

        monkeypatch.setattr(subprocess, "run", fake_run)
        minimal_config.latex.try_usetex = True
        result = render_latex_block("x = 1", minimal_config.latex, preamble=r"\csname input\endcsname{secret.tex}")
        assert called is False
        assert result.startswith("data:image/png;base64,")

    def test_render_usetex_sanitizer_ignores_commented_dangerous_command(self, minimal_config, monkeypatch):
        """Commented-out dangerous commands should not disable the usetex path."""
        calls = 0

        def fake_run(cmd, **kwargs):
            nonlocal calls
            calls += 1

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

        monkeypatch.setattr(subprocess, "run", fake_run)
        minimal_config.latex.try_usetex = True
        result = render_latex_block("x = 1", minimal_config.latex, preamble="% \\input{secret.tex}")
        assert calls >= 2
        assert result.startswith("data:image/png;base64,")

    def test_render_usetex_sanitizer_blocks_dangerous_package(self, minimal_config, monkeypatch):
        """Dangerous LaTeX packages are blocked before subprocess invocation."""
        called = False

        def fake_run(cmd, **kwargs):
            nonlocal called
            called = True
            raise RuntimeError("subprocess should not be called for blocked package")

        monkeypatch.setattr(subprocess, "run", fake_run)
        minimal_config.latex.try_usetex = True
        result = render_latex_block("x = 1", minimal_config.latex, preamble=r"\usepackage{shellesc}")
        assert called is False
        assert result.startswith("data:image/png;base64,")


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_latex(self, minimal_config):
        """Empty LaTeX string raises ValueError."""
        minimal_config.latex.try_usetex = False
        with pytest.raises(ValueError):
            render_latex_block("", minimal_config.latex)

    def test_whitespace_only(self, minimal_config):
        """Whitespace-only LaTeX raises ValueError."""
        minimal_config.latex.try_usetex = False
        with pytest.raises(ValueError):
            render_latex_block("   ", minimal_config.latex)

    def test_invalid_latex(self, minimal_config):
        """Invalid LaTeX raises ValueError."""
        minimal_config.latex.try_usetex = False
        with pytest.raises(ValueError):
            render_latex_block(r"\invalid{command}", minimal_config.latex)

    def test_very_long_expression(self, minimal_config):
        """Very long expression handled."""
        minimal_config.latex.try_usetex = False
        latex = " + ".join([f"x_{i}" for i in range(50)])
        result = render_latex_block(latex, minimal_config.latex)
        assert result.startswith("data:image/png;base64,")

    def test_nested_environments(self, minimal_config):
        """Nested LaTeX environments handled."""
        minimal_config.latex.try_usetex = False
        latex = r"\begin{equation}\frac{\sum_{i=1}^{n} x_i}{n}\end{equation}"
        result = render_latex_block(latex, minimal_config.latex)
        assert result.startswith("data:image/png;base64,")

    def test_border_radius_applied(self):
        """Border radius applied to output."""
        config = LatexConfig(
            font_size=24,
            dpi=72,
            color="black",
            background="white",
            padding=10,
            image_width=800,
            try_usetex=False,
            border_radius=15,
        )
        latex = "x = 1"
        result = render_latex_block(latex, config)
        assert result.startswith("data:image/png;base64,")

        # Verify the image has alpha channel (from rounded corners)
        b64_data = result.split(",", 1)[1]
        png_bytes = base64.b64decode(b64_data)
        img = Image.open(io.BytesIO(png_bytes))
        assert img.mode == "RGBA"
