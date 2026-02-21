"""
Unit tests for code rendering to PNG.

Tests the renderers/code_renderer.py module which renders source code and
plain-text output to syntax-highlighted PNG images.
"""
import pytest
from PIL import Image
import io
from nb2wb.renderers.code_renderer import (
    render_code,
    render_output_text,
    vstack_and_pad,
    _tokenize,
    _load_font,
    _find_font,
    _hex_to_rgb,
    _rgb_to_hex,
    _shift,
    _text_w,
    _line_height,
    _default_fg,
    _create_output_style,
    _outer_pad,
    _round_corners,
    _draw_footer,
    _draw_border,
    _PAD,
    _FOOTER_FONT_RATIO,
)
from nb2wb.config import CodeConfig
from pygments.styles import get_style_by_name


class TestRenderCode:
    """Test main code rendering function."""

    def test_render_python_code(self, minimal_config, mock_font_available):
        """Render Python code with syntax highlighting."""
        source = "x = 1 + 1\nprint(x)"
        png_bytes = render_code(source, "python", minimal_config.code)

        img = Image.open(io.BytesIO(png_bytes))
        assert img.format == "PNG"
        assert img.width > 0
        assert img.height > 0

    def test_render_javascript_code(self, minimal_config, mock_font_available):
        """Render JavaScript code."""
        source = "const x = 42;\nconsole.log(x);"
        png_bytes = render_code(source, "javascript", minimal_config.code)

        img = Image.open(io.BytesIO(png_bytes))
        assert img.format == "PNG"

    def test_render_empty_code(self, minimal_config, mock_font_available):
        """Empty code renders without crashing."""
        png_bytes = render_code("", "python", minimal_config.code)
        img = Image.open(io.BytesIO(png_bytes))
        assert img.format == "PNG"

    def test_render_with_line_numbers(self, minimal_config, mock_font_available):
        """Render with line numbers enabled."""
        config = minimal_config.code
        config.line_numbers = True
        source = "line1\nline2\nline3"
        png_bytes = render_code(source, "python", config)

        img = Image.open(io.BytesIO(png_bytes))
        assert img.width > 0
        # With line numbers, image should be wider

    def test_render_without_line_numbers(self, minimal_config, mock_font_available):
        """Render without line numbers."""
        config = minimal_config.code
        config.line_numbers = False
        source = "line1\nline2"
        png_bytes = render_code(source, "python", config)

        img = Image.open(io.BytesIO(png_bytes))
        assert img.format == "PNG"

    def test_render_with_padding(self, minimal_config, mock_font_available):
        """Render with outer padding."""
        config = minimal_config.code
        config.padding_x = 50
        config.padding_y = 50
        source = "x = 1"
        png_bytes = render_code(source, "python", config, apply_padding=True)

        img = Image.open(io.BytesIO(png_bytes))
        # With padding, image should be larger
        assert img.width >= 100  # At least padding on both sides

    def test_render_without_padding(self, minimal_config, mock_font_available):
        """Render without outer padding."""
        config = minimal_config.code
        source = "x = 1"
        png_bytes = render_code(source, "python", config, apply_padding=False)

        img = Image.open(io.BytesIO(png_bytes))
        assert img.format == "PNG"

    def test_render_long_code(self, minimal_config, mock_font_available):
        """Render long source code."""
        source = "\n".join([f"line_{i} = {i}" for i in range(100)])
        png_bytes = render_code(source, "python", minimal_config.code)

        img = Image.open(io.BytesIO(png_bytes))
        # Should be tall with many lines
        assert img.height > 1000

    def test_render_wide_code(self, minimal_config, mock_font_available):
        """Render wide source code."""
        source = "x = " + " + ".join(["1"] * 100)
        png_bytes = render_code(source, "python", minimal_config.code)

        img = Image.open(io.BytesIO(png_bytes))
        # Should respect min_width
        assert img.width >= minimal_config.code.image_width


class TestRenderOutputText:
    """Test plain-text output rendering."""

    def test_render_output_simple(self, minimal_config, mock_font_available):
        """Render simple output text."""
        text = "Hello, World!"
        png_bytes = render_output_text(text, minimal_config.code)

        img = Image.open(io.BytesIO(png_bytes))
        assert img.format == "PNG"

    def test_render_output_multiline(self, minimal_config, mock_font_available):
        """Render multiline output."""
        text = "Line 1\nLine 2\nLine 3"
        png_bytes = render_output_text(text, minimal_config.code)

        img = Image.open(io.BytesIO(png_bytes))
        assert img.height > 50  # Multiple lines should be taller

    def test_render_output_empty(self, minimal_config, mock_font_available):
        """Empty output renders without crashing."""
        png_bytes = render_output_text("", minimal_config.code)
        img = Image.open(io.BytesIO(png_bytes))
        assert img.format == "PNG"

    def test_render_output_no_line_numbers(self, minimal_config, mock_font_available):
        """Output text never has line numbers."""
        config = minimal_config.code
        config.line_numbers = True  # Should be ignored for output
        text = "Output 1\nOutput 2"
        png_bytes = render_output_text(text, config)

        img = Image.open(io.BytesIO(png_bytes))
        assert img.format == "PNG"
        # No line numbers for output (verified by not crashing)

    def test_render_output_has_margin_label(self, minimal_config, mock_font_available):
        """Output cells with '...' label are wider than without."""
        config = minimal_config.code
        config.image_width = 1  # tiny min so content width dominates
        text = "output"

        # Render output (has "..." label → wider)
        output_png = render_output_text(text, config, apply_padding=False)
        output_img = Image.open(io.BytesIO(output_png))

        # Render plain code with same text (no label → narrower)
        from nb2wb.renderers.code_renderer import _paint, _tokenize, _create_output_style
        from pygments.styles import get_style_by_name as _gsbn
        style = _gsbn(config.theme)
        font = _load_font(config.font_size)
        out_style = _create_output_style(style)
        lines = _tokenize(text, "text", style)
        plain_png = _paint(lines, font, out_style, show_line_numbers=False,
                           min_width=config.image_width)
        plain_img = Image.open(io.BytesIO(plain_png))

        # The output image should be wider due to the label margin
        assert output_img.width > plain_img.width

    def test_render_code_has_footer_standalone(self, minimal_config, mock_font_available):
        """Standalone code cells (apply_padding=True) include footer bar."""
        config = minimal_config.code
        config.line_numbers = False
        source = "x = 1"

        # Render without footer for baseline height
        from nb2wb.renderers.code_renderer import _paint, _tokenize
        from pygments.styles import get_style_by_name as _gsbn
        style = _gsbn(config.theme)
        font = _load_font(config.font_size)
        lines = _tokenize(source, "python", style)
        base_png = _paint(lines, font, style, show_line_numbers=False,
                          min_width=config.image_width)
        base_img = Image.open(io.BytesIO(base_png))

        # Render standalone (has footer)
        code_png = render_code(source, "python", config, apply_padding=True)
        code_img = Image.open(io.BytesIO(code_png))

        # Standalone image is taller (footer + border + padding)
        assert code_img.height > base_img.height

    def test_render_code_no_footer_without_padding(self, minimal_config, mock_font_available):
        """Stacking mode (apply_padding=False) omits footer (drawn by vstack)."""
        config = minimal_config.code
        config.line_numbers = False
        source = "x = 1"

        from nb2wb.renderers.code_renderer import _paint, _tokenize
        from pygments.styles import get_style_by_name as _gsbn
        style = _gsbn(config.theme)
        font = _load_font(config.font_size)
        lines = _tokenize(source, "python", style)
        base_png = _paint(lines, font, style, show_line_numbers=False,
                          min_width=config.image_width)
        base_img = Image.open(io.BytesIO(base_png))

        code_png = render_code(source, "python", config, apply_padding=False)
        code_img = Image.open(io.BytesIO(code_png))

        # Without padding the image should match the raw paint output
        assert code_img.height == base_img.height

    def test_vstack_draws_footer(self, minimal_config, mock_font_available):
        """vstack_and_pad draws the footer when code_footer params are given."""
        config = minimal_config.code
        config.line_numbers = False
        source = "x = 1"

        code_png = render_code(source, "python", config, apply_padding=False)
        base_img = Image.open(io.BytesIO(code_png))

        result = vstack_and_pad([code_png], config,
                                code_footer_left="[1]",
                                code_footer_right="Python")
        result_img = Image.open(io.BytesIO(result))

        # After adding footer + padding the image should be taller
        assert result_img.height > base_img.height

    def test_render_code_has_border_with_padding(self, minimal_config, mock_font_available):
        """Code cells have a thin border when rendered standalone (apply_padding=True)."""
        config = minimal_config.code
        config.theme = "monokai"
        config.padding_x = 10
        config.padding_y = 10
        source = "x = 1"
        png_bytes = render_code(source, "python", config, apply_padding=True)
        img = Image.open(io.BytesIO(png_bytes))

        # Border sits at (padding_x, padding_y); interior is deeper inside
        border_pixel = img.getpixel((config.padding_x, config.padding_y))
        interior_pixel = img.getpixel((img.width // 2, config.padding_y + _PAD))
        assert border_pixel != interior_pixel, "border should differ from interior"

    def test_render_code_no_border_without_padding(self, minimal_config, mock_font_available):
        """Code cells have no border when apply_padding=False (deferred to vstack)."""
        config = minimal_config.code
        config.theme = "monokai"
        source = "x = 1"
        png_bytes = render_code(source, "python", config, apply_padding=False)
        img = Image.open(io.BytesIO(png_bytes))

        # Without padding the edge and one pixel inward should share the bg
        edge_pixel = img.getpixel((0, 0))
        near_edge = img.getpixel((1, 0))
        assert edge_pixel == near_edge, "no border when apply_padding=False"

    def test_output_has_no_border(self, minimal_config, mock_font_available):
        """Output cells have no border — edge matches interior bg."""
        config = minimal_config.code
        config.theme = "monokai"
        text = "some output"
        png_bytes = render_output_text(text, config, apply_padding=False)
        img = Image.open(io.BytesIO(png_bytes))

        # For output, the top-left pixel should be the output bg (no border)
        top_left = img.getpixel((0, 0))
        # Sample interior bg at top-right area (away from label)
        top_right = img.getpixel((img.width - 1, 0))
        assert top_left == top_right, "output should have uniform bg at edges"


class TestVStackAndPad:
    """Test vertical image stacking."""

    def test_vstack_empty_raises(self, minimal_config):
        """Empty input list is rejected with a clear error."""
        with pytest.raises(ValueError, match="png_list must not be empty"):
            vstack_and_pad([], minimal_config.code)

    def test_vstack_single_image(self, minimal_config, mock_font_available):
        """Single image passed through."""
        source = "x = 1"
        png1 = render_code(source, "python", minimal_config.code, apply_padding=False)

        result = vstack_and_pad([png1], minimal_config.code)
        img = Image.open(io.BytesIO(result))
        assert img.format == "PNG"

    def test_vstack_multiple_images(self, minimal_config, mock_font_available):
        """Stack multiple images vertically."""
        source1 = "x = 1"
        source2 = "y = 2"
        png1 = render_code(source1, "python", minimal_config.code, apply_padding=False)
        png2 = render_code(source2, "python", minimal_config.code, apply_padding=False)

        result = vstack_and_pad([png1, png2], minimal_config.code)
        img = Image.open(io.BytesIO(result))

        # Stacked image should be taller
        img1 = Image.open(io.BytesIO(png1))
        img2 = Image.open(io.BytesIO(png2))
        expected_height = img1.height + img2.height + minimal_config.code.separator
        # Allow some tolerance for padding
        assert img.height >= expected_height - 50

    def test_vstack_with_separator(self, minimal_config, mock_font_available):
        """Separator gap applied between images."""
        config = minimal_config.code
        config.separator = 100

        source1 = "x = 1"
        source2 = "y = 2"
        png1 = render_code(source1, "python", config, apply_padding=False)
        png2 = render_code(source2, "python", config, apply_padding=False)

        result = vstack_and_pad([png1, png2], config)
        img = Image.open(io.BytesIO(result))
        assert img.format == "PNG"

    def test_vstack_with_border_radius(self, minimal_config, mock_font_available):
        """Border radius applied after stacking."""
        config = minimal_config.code
        config.border_radius = 15

        source1 = "x = 1"
        png1 = render_code(source1, "python", config, apply_padding=False)

        result = vstack_and_pad([png1], config)
        img = Image.open(io.BytesIO(result))

        # With border radius, should have alpha channel
        assert img.mode == "RGBA"


class TestTokenize:
    """Test Pygments tokenization."""

    def test_tokenize_python(self):
        """Tokenize Python source."""
        source = "x = 1"
        style = get_style_by_name("default")
        lines = _tokenize(source, "python", style)

        assert len(lines) >= 1
        assert isinstance(lines[0], list)

    def test_tokenize_javascript(self):
        """Tokenize JavaScript source."""
        source = "const x = 42;"
        style = get_style_by_name("default")
        lines = _tokenize(source, "javascript", style)

        assert len(lines) >= 1

    def test_tokenize_multiline(self):
        """Tokenize multiline source."""
        source = "line1\nline2\nline3"
        style = get_style_by_name("default")
        lines = _tokenize(source, "text", style)

        assert len(lines) == 3

    def test_tokenize_empty(self):
        """Tokenize empty source."""
        style = get_style_by_name("default")
        lines = _tokenize("", "python", style)

        # Should return at least one line
        assert len(lines) >= 1

    def test_tokenize_unknown_language(self):
        """Unknown language falls back to TextLexer."""
        source = "some text"
        style = get_style_by_name("default")
        lines = _tokenize(source, "unknown_language", style)

        # Should not crash, returns tokenized text
        assert len(lines) >= 1

    def test_tokenize_guess_language(self):
        """Language guessing works when lexer fails."""
        source = "def foo():\n    pass"
        style = get_style_by_name("default")
        # Use invalid language name to trigger guessing
        lines = _tokenize(source, "invalid", style)

        assert len(lines) >= 1


class TestFontLoading:
    """Test font loading and fallback."""

    def test_load_font_basic(self, mock_font_available):
        """Load font with basic size."""
        font = _load_font(24)
        assert font is not None

    def test_load_font_large_size(self, mock_font_available):
        """Load font with large size."""
        font = _load_font(72)
        assert font is not None

    def test_load_font_small_size(self, mock_font_available):
        """Load font with small size."""
        font = _load_font(12)
        assert font is not None

    def test_find_font_returns_path_or_none(self):
        """_find_font returns path or None."""
        result = _find_font()
        # Either a path string or None
        assert result is None or isinstance(result, str)


class TestColorHelpers:
    """Test color conversion and manipulation."""

    def test_hex_to_rgb_six_digits(self):
        """Convert 6-digit hex to RGB."""
        result = _hex_to_rgb("#FF0000")
        assert result == (255, 0, 0)

    def test_hex_to_rgb_no_hash(self):
        """Hex without # handled."""
        result = _hex_to_rgb("00FF00")
        assert result == (0, 255, 0)

    def test_hex_to_rgb_three_digits(self):
        """Convert 3-digit hex to RGB."""
        result = _hex_to_rgb("#F0F")
        assert result == (255, 0, 255)

    def test_hex_to_rgb_invalid(self):
        """Invalid hex returns default gray."""
        result = _hex_to_rgb("invalid")
        assert result == (200, 200, 200)

    def test_hex_to_rgb_empty(self):
        """Empty string returns default gray."""
        result = _hex_to_rgb("")
        assert result == (200, 200, 200)

    def test_rgb_to_hex(self):
        """Convert RGB to hex."""
        result = _rgb_to_hex((255, 0, 0))
        assert result == "#ff0000"

    def test_rgb_to_hex_lowercase(self):
        """RGB to hex returns lowercase."""
        result = _rgb_to_hex((170, 187, 204))
        assert result.startswith("#")
        assert len(result) == 7

    def test_shift_brighten(self):
        """Brighten color by positive amount."""
        rgb = (100, 100, 100)
        result = _shift(rgb, 50)
        assert result == (150, 150, 150)

    def test_shift_darken(self):
        """Darken color by negative amount."""
        rgb = (100, 100, 100)
        result = _shift(rgb, -50)
        assert result == (50, 50, 50)

    def test_shift_clamp_max(self):
        """Shift clamps at 255."""
        rgb = (250, 250, 250)
        result = _shift(rgb, 50)
        assert result == (255, 255, 255)

    def test_shift_clamp_min(self):
        """Shift clamps at 0."""
        rgb = (10, 10, 10)
        result = _shift(rgb, -50)
        assert result == (0, 0, 0)

    def test_default_fg_light_theme(self):
        """Default foreground for light theme."""
        style = get_style_by_name("default")
        fg = _default_fg(style)
        # Should be tuple of 3 ints
        assert len(fg) == 3
        assert all(isinstance(c, int) for c in fg)

    def test_default_fg_dark_theme(self):
        """Default foreground for dark theme."""
        style = get_style_by_name("monokai")
        fg = _default_fg(style)
        assert len(fg) == 3

    def test_create_output_style_lighter(self):
        """Output style is lighter than base."""
        base_style = get_style_by_name("monokai")
        output_style = _create_output_style(base_style)

        # Should have lighter background
        assert hasattr(output_style, "background_color")
        assert output_style.background_color != base_style.background_color


class TestMeasurementHelpers:
    """Test text measurement utilities."""

    def test_text_w_basic(self, mock_font_available):
        """Measure text width."""
        font = _load_font(24)
        width = _text_w("hello", font)
        assert width > 0

    def test_text_w_empty(self, mock_font_available):
        """Empty text has zero or minimal width."""
        font = _load_font(24)
        width = _text_w("", font)
        assert width >= 0

    def test_text_w_long_text(self, mock_font_available):
        """Long text has larger width."""
        font = _load_font(24)
        short = _text_w("x", font)
        long = _text_w("x" * 100, font)
        assert long > short

    def test_line_height_basic(self, mock_font_available):
        """Calculate line height."""
        font = _load_font(24)
        height = _line_height(font)
        assert height > 0

    def test_line_height_with_gap(self, mock_font_available):
        """Line height includes gap."""
        font = _load_font(24)
        height_no_gap = _line_height(font, gap=0)
        height_gap = _line_height(font, gap=10)
        assert height_gap >= height_no_gap


class TestImageProcessing:
    """Test image processing utilities."""

    def test_outer_pad_basic(self, minimal_config, mock_font_available):
        """Apply outer padding to image."""
        source = "x = 1"
        png = render_code(source, "python", minimal_config.code, apply_padding=False)

        padded = _outer_pad(png, 50, 50, "white")

        img_orig = Image.open(io.BytesIO(png))
        img_padded = Image.open(io.BytesIO(padded))

        # Padded should be larger
        assert img_padded.width == img_orig.width + 100
        assert img_padded.height == img_orig.height + 100

    def test_outer_pad_zero_padding(self, minimal_config, mock_font_available):
        """Zero padding returns similar size."""
        source = "x = 1"
        png = render_code(source, "python", minimal_config.code, apply_padding=False)

        padded = _outer_pad(png, 0, 0, "white")

        img_orig = Image.open(io.BytesIO(png))
        img_padded = Image.open(io.BytesIO(padded))

        assert img_padded.width == img_orig.width
        assert img_padded.height == img_orig.height

    def test_round_corners_basic(self, minimal_config, mock_font_available):
        """Apply rounded corners to image."""
        source = "x = 1"
        png = render_code(source, "python", minimal_config.code, apply_padding=False)
        img = Image.open(io.BytesIO(png))

        rounded = _round_corners(img, 15)

        # Should have alpha channel
        assert rounded.mode == "RGBA"
        assert rounded.size == img.size

    def test_round_corners_zero_radius(self, minimal_config, mock_font_available):
        """Zero radius rounded corners still works."""
        source = "x = 1"
        png = render_code(source, "python", minimal_config.code, apply_padding=False)
        img = Image.open(io.BytesIO(png))

        rounded = _round_corners(img, 0)
        assert rounded.mode == "RGBA"


class TestVStackWidthConsistency:
    """Verify that stacked code and output cells share the same width."""

    def test_code_and_output_same_width_at_min(self, minimal_config, mock_font_available):
        """Code and output cells match width when both fit within min_width."""
        config = minimal_config.code
        config.line_numbers = True
        code_png = render_code("x = 1", "python", config, apply_padding=False)
        output_png = render_output_text("2", config, apply_padding=False)

        result = vstack_and_pad([code_png, output_png], config)
        img = Image.open(io.BytesIO(result))

        # Extract individual sub-images from the stack to check uniformity
        code_img = Image.open(io.BytesIO(code_png))
        output_img = Image.open(io.BytesIO(output_png))

        # The combined image width must be consistent throughout
        assert img.width >= max(code_img.width, output_img.width)

    def test_code_wider_than_output_extends_output(self, minimal_config, mock_font_available):
        """When code cell exceeds min_width, output cell is extended to match."""
        config = minimal_config.code
        config.line_numbers = True
        # Long line that pushes the code cell beyond image_width
        wide_source = "x = " + " + ".join(["variable"] * 20)
        code_png = render_code(wide_source, "python", config, apply_padding=False)
        output_png = render_output_text("42", config, apply_padding=False)

        code_img = Image.open(io.BytesIO(code_png))
        output_img = Image.open(io.BytesIO(output_png))
        assert code_img.width > output_img.width, "precondition: code must be wider"

        result = vstack_and_pad([code_png, output_png], config)
        combined = Image.open(io.BytesIO(result))

        # Sample a horizontal line in the output region — every pixel should
        # belong to the output background, not the separator/padding color.
        output_y = code_img.height + config.separator + 2  # inside the output region
        strip = [combined.getpixel((x, output_y)) for x in range(combined.width)]
        # The rightmost pixel of the output region must match the output bg,
        # not the separator colour.
        right_edge = strip[-1]
        left_edge = strip[0]
        # Both edges should be the same colour (the output background)
        assert right_edge == left_edge

    def test_output_wider_than_code_extends_code(self, minimal_config, mock_font_available):
        """When output cell exceeds min_width, code cell is extended to match."""
        config = minimal_config.code
        config.line_numbers = False
        config.image_width = 200  # low min so content width dominates
        code_png = render_code("x = 1", "python", config, apply_padding=False)
        wide_output = "result: " + " ".join(["value"] * 30)
        output_png = render_output_text(wide_output, config, apply_padding=False)

        code_img = Image.open(io.BytesIO(code_png))
        output_img = Image.open(io.BytesIO(output_png))
        assert output_img.width > code_img.width, "precondition: output must be wider"

        result = vstack_and_pad([code_png, output_png], config)
        combined = Image.open(io.BytesIO(result))

        # Sample a horizontal line in the code region
        code_y = 2  # inside the code region
        strip = [combined.getpixel((x, code_y)) for x in range(combined.width)]
        right_edge = strip[-1]
        left_edge = strip[0]
        assert right_edge == left_edge

    def test_multiple_outputs_all_same_width(self, minimal_config, mock_font_available):
        """Three images of different natural widths all get the same final width."""
        config = minimal_config.code
        config.line_numbers = True
        config.image_width = 200

        wide_code = "x = " + " + ".join(["variable"] * 20)
        code_png = render_code(wide_code, "python", config, apply_padding=False)
        out1_png = render_output_text("short", config, apply_padding=False)
        out2_png = render_output_text("a slightly longer output line here", config, apply_padding=False)

        imgs = [Image.open(io.BytesIO(b)) for b in [code_png, out1_png, out2_png]]
        widths = {img.width for img in imgs}
        assert len(widths) > 1, "precondition: inputs should have different widths"

        result = vstack_and_pad([code_png, out1_png, out2_png], config)
        combined = Image.open(io.BytesIO(result))

        # Walk through each sub-image region and verify full-width fill
        expected_w = combined.width
        y = 0
        for i, img in enumerate(imgs):
            sample_y = y + 2
            if sample_y < combined.height:
                strip = [combined.getpixel((x, sample_y)) for x in range(expected_w)]
                assert strip[0] == strip[-1], f"image {i}: edges should match"
            y += img.height + (config.separator if i < len(imgs) - 1 else 0)


class TestVStackCodeBorder:
    """Verify that vstack_and_pad draws borders after width normalisation."""

    def test_single_code_image_gets_border(self, minimal_config, mock_font_available):
        """Single code image receives border via draw_code_border."""
        config = minimal_config.code
        config.theme = "monokai"
        code_png = render_code("x = 1", "python", config, apply_padding=False)

        result = vstack_and_pad([code_png], config, draw_code_border=True)
        img = Image.open(io.BytesIO(result))

        # After padding the border sits at (padding_x, padding_y)
        border_pixel = img.getpixel((config.padding_x, config.padding_y))
        interior_pixel = img.getpixel((img.width // 2, config.padding_y + _PAD))
        assert border_pixel != interior_pixel, "border should differ from interior"

    def test_border_spans_full_width_when_output_wider(self, minimal_config, mock_font_available):
        """When output is wider than code, the border extends to the full width."""
        config = minimal_config.code
        config.theme = "monokai"
        config.line_numbers = False
        config.image_width = 200
        config.padding_x = 0
        config.padding_y = 0

        code_png = render_code("x = 1", "python", config, apply_padding=False)
        wide_output = "result: " + " ".join(["value"] * 30)
        output_png = render_output_text(wide_output, config, apply_padding=False)

        code_img = Image.open(io.BytesIO(code_png))
        output_img = Image.open(io.BytesIO(output_png))
        assert output_img.width > code_img.width, "precondition: output wider"

        result = vstack_and_pad([code_png, output_png], config,
                                draw_code_border=True)
        combined = Image.open(io.BytesIO(result))

        # Border top-left corner should equal top-right corner (border at full width)
        top_left = combined.getpixel((0, 0))
        top_right = combined.getpixel((combined.width - 1, 0))
        assert top_left == top_right, "border should span full combined width"

    def test_no_border_without_flag(self, minimal_config, mock_font_available):
        """Without draw_code_border the code region has no border."""
        config = minimal_config.code
        config.theme = "monokai"
        config.padding_x = 0
        config.padding_y = 0

        code_png = render_code("x = 1", "python", config, apply_padding=False)
        result = vstack_and_pad([code_png], config, draw_code_border=False)
        img = Image.open(io.BytesIO(result))

        # Edge and one pixel inward should share the same background colour
        edge = img.getpixel((0, 0))
        near = img.getpixel((1, 0))
        assert edge == near, "no border expected without draw_code_border"

    def test_code_background_fills_extended_region(self, minimal_config, mock_font_available):
        """Extended code region is filled with code background, not border color."""
        config = minimal_config.code
        config.theme = "monokai"
        config.line_numbers = False
        config.image_width = 200
        config.padding_x = 0
        config.padding_y = 0

        code_png = render_code("x = 1", "python", config, apply_padding=False)
        wide_output = "result: " + " ".join(["value"] * 30)
        output_png = render_output_text(wide_output, config, apply_padding=False)

        code_img = Image.open(io.BytesIO(code_png))
        output_img = Image.open(io.BytesIO(output_png))
        assert output_img.width > code_img.width, "precondition: output wider"

        result = vstack_and_pad([code_png, output_png], config,
                                draw_code_border=True)
        combined = Image.open(io.BytesIO(result))

        # Interior of the code region (row 1, past border) should be uniform
        # across the full width — original area and extended area
        interior_left = combined.getpixel((1, 1))
        interior_right = combined.getpixel((combined.width - 2, 1))
        assert interior_left == interior_right, \
            "code background should be uniform across extended width"

    def test_footer_extends_to_full_width(self, minimal_config, mock_font_available):
        """Footer bar extends to the full combined width when code is narrower."""
        config = minimal_config.code
        config.theme = "monokai"
        config.line_numbers = False
        config.image_width = 200
        config.padding_x = 0
        config.padding_y = 0

        code_png = render_code("x = 1", "python", config, apply_padding=False)
        wide_output = "result: " + " ".join(["value"] * 30)
        output_png = render_output_text(wide_output, config, apply_padding=False)

        code_img = Image.open(io.BytesIO(code_png))
        output_img = Image.open(io.BytesIO(output_png))
        assert output_img.width > code_img.width, "precondition: output wider"

        result = vstack_and_pad([code_png, output_png], config,
                                draw_code_border=True,
                                code_footer_left="[1]",
                                code_footer_right="Python")
        combined = Image.open(io.BytesIO(result))

        # The footer is drawn after width normalisation, so its background
        # must span the full combined width.  The code image without footer
        # occupies the top rows; the footer sits just below that.
        footer_y = code_img.height + 3  # a few pixels into the footer region
        footer_left = combined.getpixel((1, footer_y))
        footer_right = combined.getpixel((combined.width - 2, footer_y))
        assert footer_left == footer_right, \
            "footer background should extend to full combined width"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_render_special_characters(self, minimal_config, mock_font_available):
        """Render code with special characters."""
        source = 'x = "hello\nworld\t!"'
        png_bytes = render_code(source, "python", minimal_config.code)
        img = Image.open(io.BytesIO(png_bytes))
        assert img.format == "PNG"

    def test_render_unicode_characters(self, minimal_config, mock_font_available):
        """Render code with Unicode."""
        source = "# Comment with emoji 🚀\nx = 'Hello 世界'"
        png_bytes = render_code(source, "python", minimal_config.code)
        img = Image.open(io.BytesIO(png_bytes))
        assert img.format == "PNG"

    def test_render_very_long_line(self, minimal_config, mock_font_available):
        """Render single very long line."""
        source = "x = " + "1" * 1000
        png_bytes = render_code(source, "python", minimal_config.code)
        img = Image.open(io.BytesIO(png_bytes))
        # Should handle gracefully
        assert img.width >= minimal_config.code.image_width

    def test_render_many_lines(self, minimal_config, mock_font_available):
        """Render many lines of code."""
        source = "\n".join([f"line{i} = {i}" for i in range(1000)])
        png_bytes = render_code(source, "python", minimal_config.code)
        img = Image.open(io.BytesIO(png_bytes))
        # Should be very tall
        assert img.height > 5000

    def test_render_different_themes(self, minimal_config, mock_font_available):
        """Render with different Pygments themes."""
        source = "x = 1"
        for theme in ["default", "monokai", "github-dark"]:
            config = minimal_config.code
            config.theme = theme
            png_bytes = render_code(source, "python", config)
            img = Image.open(io.BytesIO(png_bytes))
            assert img.format == "PNG"
