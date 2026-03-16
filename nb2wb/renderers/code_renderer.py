"""
Render source code and plain-text output to PNG images using PIL + Pygments.

Each image is returned as raw PNG bytes; callers base64-encode them for
embedding in HTML.
"""
from __future__ import annotations

import io
import inspect
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import get_lexer_by_name, guess_lexer, TextLexer
from pygments.styles import get_style_by_name
from pygments.token import Token

from ..config import CodeConfig
from ._image_utils import round_corners as _round_corners

# ---------------------------------------------------------------------------
# Platform font candidates (first existing path wins)
# ---------------------------------------------------------------------------
_FONT_CANDIDATES: dict[str, list[str]] = {
    "linux": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf",
        "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    ],
    "darwin": [
        "/System/Library/Fonts/Supplemental/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
        "/Library/Fonts/Courier New.ttf",
    ],
    "win32": [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "C:/Windows/Fonts/lucon.ttf",
    ],
}

_PAD = 24       # inner padding in pixels around text content
_LINE_GAP = 4   # extra vertical space between lines
_FOOTER_FONT_RATIO = 0.58  # footer/label font size relative to main font


def _png_to_image(png_bytes: bytes) -> Image.Image:
    """Decode PNG bytes into an RGB Pillow image.

    Args:
        png_bytes: Raw PNG image bytes to decode.

    Returns:
        A Pillow image converted to RGB mode.
    """
    return Image.open(io.BytesIO(png_bytes)).convert("RGB")


def _image_to_png(image: Image.Image) -> bytes:
    """Encode a Pillow image as PNG bytes.

    Args:
        image: Pillow image to encode.

    Returns:
        Raw PNG bytes for the image.
    """
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _border_color(bg: tuple[int, int, int]) -> tuple[int, int, int]:
    """Choose a visible border color against a background color.

    Args:
        bg: Background color as an RGB tuple.

    Returns:
        A contrasting RGB tuple suitable for a border.
    """
    brightness = sum(bg) / 3
    return _shift(bg, 40 if brightness < 128 else -40)


def _extend_image_width(image: Image.Image, width: int) -> Image.Image:
    """Extend an image to a target width by repeating its right edge.

    Args:
        image: Source image to widen.
        width: Target width in pixels.

    Returns:
        The widened image, or the original image when already wide enough.
    """
    if image.width >= width:
        return image
    right_col = image.crop((image.width - 1, 0, image.width, image.height))
    fill = right_col.resize((width - image.width, image.height), Image.NEAREST)
    extended = Image.new("RGB", (width, image.height))
    extended.paste(image, (0, 0))
    extended.paste(fill, (image.width, 0))
    return extended


def _normalize_image_widths(images: list[Image.Image]) -> list[Image.Image]:
    """Extend all images to match the widest image in the list.

    Args:
        images: Images that should share one common width.

    Returns:
        Images normalized to a consistent width.
    """
    if not images:
        return images
    width = max(img.width for img in images)
    return [_extend_image_width(img, width) for img in images]


def _stack_images(images: list[Image.Image], separator: int, sep_color: str) -> Image.Image:
    """Stack images vertically with a configurable separator between them.

    Args:
        images: Images to stack in order from top to bottom.
        separator: Vertical gap between stacked images in pixels.
        sep_color: Background color used for separator rows.

    Returns:
        A new stacked Pillow image.
    """
    width = max(img.width for img in images)
    total_h = sum(img.height for img in images) + separator * (len(images) - 1)
    combined = Image.new("RGB", (width, total_h), _hex_to_rgb(sep_color))
    y = 0
    for index, img in enumerate(images):
        combined.paste(img, (0, y))
        y += img.height
        if index < len(images) - 1:
            y += separator
    return combined


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_code(source: str, language: str, config: CodeConfig, *,
                apply_padding: bool = True,
                execution_count: Optional[int] = None) -> bytes:
    """Render source code with syntax highlighting to PNG bytes.

    Args:
        source: Source code text to render.
        language: Language name used for syntax highlighting.
        config: Active code rendering configuration.
        apply_padding: Whether to add footer, border, and outer padding.
        execution_count: Optional execution count label for the footer.

    Returns:
        PNG bytes for the rendered code image.
    """
    font = _load_font(config.font_size)
    style_cls = _style_for_theme(config.theme)
    lines = _tokenize(source, language, style_cls)
    png = _paint(lines, font, style_cls, show_line_numbers=config.line_numbers,
                 min_width=config.image_width)

    if apply_padding:
        # Standalone rendering: draw footer, border, and padding now.
        ec_text = f"[{execution_count}]" if execution_count is not None else "[ ]"
        lang_display = language.capitalize() if language else ""
        image = _png_to_image(png)
        image = _draw_footer_image(
            image,
            style_cls,
            config,
            left_text=ec_text,
            right_text=lang_display,
        )
        image = _draw_border_image(image, style_cls)
        if config.padding_x or config.padding_y:
            bg = config.background or style_cls.background_color
            image = _outer_pad_image(image, config.padding_x, config.padding_y, bg)
        png = _image_to_png(image)
    # When apply_padding is False the caller is expected to stack this image
    # via vstack_and_pad which draws footer, border, and padding *after*
    # normalising widths so that everything spans the full combined width.
    return png


def render_output_text(text: str, config: CodeConfig, *,
                       apply_padding: bool = True) -> bytes:
    """Render plain-text output to PNG bytes with lighter styling.

    Args:
        text: Plain-text output such as stdout, repr, or tracebacks.
        config: Active code rendering configuration.
        apply_padding: Whether to add outer padding after rendering.

    Returns:
        PNG bytes for the rendered output image.
    """
    font = _load_font(config.font_size)
    style_cls = _style_for_theme(config.theme)
    lines = _tokenize(text, "text", style_cls)

    # Create a lighter version of the style for outputs
    output_style = _create_output_style(style_cls)

    png = _paint(lines, font, output_style, show_line_numbers=False,
                 min_width=config.image_width,
                 left_margin_label="...")
    if apply_padding and (config.padding_x or config.padding_y):
        bg = config.background or output_style.background_color
        png = _outer_pad(png, config.padding_x, config.padding_y, bg)
    return png


def vstack_and_pad(png_list: list[bytes], config: CodeConfig, *,
                   draw_code_border: bool = False,
                   code_footer_left: str = "",
                   code_footer_right: str = "") -> bytes:
    """Stack PNG images vertically with separator gaps, then apply outer padding once.

    When *draw_code_border* is True the first image in the stack is treated as
    a code cell and receives a thin border **after** all images have been
    normalised to the same width.  This ensures the border spans the full
    combined width even when a later output image is wider.

    *code_footer_left* / *code_footer_right* are drawn as a Jupyter-style
    footer bar on the code cell (first image) **after** width normalisation so
    that the right-aligned text sits at the true right edge.

    Args:
        png_list: PNG images to stack from top to bottom.
        config: Active code rendering configuration.
        draw_code_border: Whether to draw a border around the first image.
        code_footer_left: Left-aligned footer text for the first image.
        code_footer_right: Right-aligned footer text for the first image.

    Returns:
        PNG bytes for the combined stacked image.
    """
    if not png_list:
        raise ValueError("png_list must not be empty")

    style_cls = _style_for_theme(config.theme)
    output_bg = _create_output_style(style_cls).background_color
    sep_color = config.background or output_bg
    has_footer = bool(code_footer_left or code_footer_right)
    images = [_png_to_image(data) for data in png_list]
    images = _normalize_image_widths(images)

    if has_footer:
        images[0] = _draw_footer_image(
            images[0],
            style_cls,
            config,
            left_text=code_footer_left,
            right_text=code_footer_right,
        )

    if len(images) == 1:
        combined = images[0]
        if draw_code_border:
            combined = _draw_border_image(combined, style_cls)
    else:
        combined = _stack_images(images, config.separator, sep_color)
        if draw_code_border:
            _draw_border_on_region(combined, style_cls, region_height=images[0].height)

    if config.padding_x or config.padding_y:
        combined = _outer_pad_image(
            combined,
            config.padding_x,
            config.padding_y,
            sep_color,
        )
    if config.border_radius:
        combined = _round_corners(combined, config.border_radius)
    return _image_to_png(combined)


# ---------------------------------------------------------------------------
# Rendering internals
# ---------------------------------------------------------------------------


def _outer_pad(png_bytes: bytes, padding_x: int, padding_y: int, background: str) -> bytes:
    """Wrap PNG bytes with outer padding of the given background color.

    Args:
        png_bytes: Raw PNG bytes to pad.
        padding_x: Horizontal padding in pixels.
        padding_y: Vertical padding in pixels.
        background: Background color used for the padding area.

    Returns:
        PNG bytes for the padded image.
    """
    img = _png_to_image(png_bytes)
    return _image_to_png(_outer_pad_image(img, padding_x, padding_y, background))


def _outer_pad_image(
    image: Image.Image,
    padding_x: int,
    padding_y: int,
    background: str,
) -> Image.Image:
    """Wrap a Pillow image with outer padding using the same image mode.

    Args:
        image: Source image to pad.
        padding_x: Horizontal padding in pixels.
        padding_y: Vertical padding in pixels.
        background: Background color used for the padding area.

    Returns:
        A new padded Pillow image.
    """
    if padding_x == 0 and padding_y == 0:
        return image
    canvas = Image.new(
        image.mode,
        (image.width + 2 * padding_x, image.height + 2 * padding_y),
        background,
    )
    canvas.paste(image, (padding_x, padding_y))
    return canvas


def _draw_footer_image(
    image: Image.Image,
    style_cls,
    config: CodeConfig,
    *,
    left_text: str,
    right_text: str,
) -> Image.Image:
    """Append a Jupyter-style footer bar to a code cell image.

    Args:
        image: Source code image to extend with a footer.
        style_cls: Pygments style used to derive footer colors.
        config: Active code rendering configuration.
        left_text: Left-aligned footer text.
        right_text: Right-aligned footer text.

    Returns:
        A new image containing the original content and footer bar.
    """
    bg = _hex_to_rgb(style_cls.background_color)
    footer_bg = _shift(bg, -12)

    footer_font = _load_font(max(int(config.font_size * _FOOTER_FONT_RATIO), 12))
    footer_lh = _line_height(footer_font, gap=0)
    footer_h = footer_lh + _PAD
    line_color = _shift(bg, -25)
    text_color = _shift(bg, 50 if sum(bg) / 3 < 128 else -50)

    # New canvas: original image + 1px separator + footer
    new_h = image.height + 1 + footer_h
    canvas = Image.new("RGB", (image.width, new_h), footer_bg)
    canvas.paste(image, (0, 0))
    draw = ImageDraw.Draw(canvas)

    # Separator line at bottom of code area
    draw.line([(0, image.height), (image.width, image.height)], fill=line_color, width=1)

    # Footer text
    text_y = image.height + 1 + (footer_h - footer_lh) // 2
    draw.text((_PAD, text_y), left_text, font=footer_font, fill=text_color)
    right_w = int(_text_w(right_text, footer_font))
    draw.text((image.width - right_w - _PAD, text_y), right_text, font=footer_font, fill=text_color)
    return canvas


def _draw_border_on_region(image: Image.Image, style_cls, *, region_height: int) -> None:
    """Draw a thin border around the top region of an image.

    Args:
        image: Image whose top region should receive a border.
        style_cls: Pygments style used to derive border colors.
        region_height: Height in pixels of the bordered region.

    Returns:
        ``None``. The border is drawn onto the image in place.
    """
    draw = ImageDraw.Draw(image)
    bg = _hex_to_rgb(style_cls.background_color)
    draw.rectangle(
        [0, 0, image.width - 1, region_height - 1],
        outline=_border_color(bg),
        width=1,
    )


def _draw_border_image(image: Image.Image, style_cls) -> Image.Image:
    """Draw a thin border around the full image.

    Args:
        image: Image that should receive a full border.
        style_cls: Pygments style used to derive border colors.

    Returns:
        The same image object after the border is drawn.
    """
    _draw_border_on_region(image, style_cls, region_height=image.height)
    return image


def _draw_footer(png_bytes: bytes, style_cls, config: CodeConfig, *,
                 left_text: str, right_text: str) -> bytes:
    """Append a Jupyter-style footer bar to encoded PNG image bytes.

    Args:
        png_bytes: Source PNG bytes to extend.
        style_cls: Pygments style used to derive footer colors.
        config: Active code rendering configuration.
        left_text: Left-aligned footer text.
        right_text: Right-aligned footer text.

    Returns:
        PNG bytes for the footer-extended image.
    """
    image = _png_to_image(png_bytes)
    return _image_to_png(
        _draw_footer_image(
            image,
            style_cls,
            config,
            left_text=left_text,
            right_text=right_text,
        )
    )


def _draw_border(png_bytes: bytes, style_cls) -> bytes:
    """Draw a thin border rectangle around encoded PNG bytes.

    Args:
        png_bytes: Source PNG bytes to decorate.
        style_cls: Pygments style used to derive border colors.

    Returns:
        PNG bytes for the bordered image.
    """
    image = _png_to_image(png_bytes)
    return _image_to_png(_draw_border_image(image, style_cls))


def _paint(
    lines: list[list[tuple[tuple[int, int, int], str]]],
    font: ImageFont.FreeTypeFont,
    style_cls,
    show_line_numbers: bool,
    min_width: int = 0,
    left_margin_label: Optional[str] = None,
) -> bytes:
    """Render tokenized lines onto a Pillow image.

    Args:
        lines: Tokenized lines as ``[(color, text), ...]`` segments.
        font: Font used for code text rendering.
        style_cls: Pygments style used for colors and background.
        show_line_numbers: Whether to render a line-number gutter.
        min_width: Minimum output width in pixels.
        left_margin_label: Optional label rendered in the left margin.

    Returns:
        Raw PNG bytes for the rendered image.
    """
    if not lines:
        lines = [[(200, 200, 200), ""]]

    lh = _line_height(font)
    bg = _hex_to_rgb(style_cls.background_color)

    # Left margin label (e.g., "..." for output cells)
    label_w = 0
    label_font = None
    if left_margin_label:
        label_font_size = max(int(getattr(font, "size", 24) * _FOOTER_FONT_RATIO), 12)
        label_font = _load_font(label_font_size)
        label_w = int(_text_w(left_margin_label, label_font)) + _PAD // 2

    # Line-number column width
    ln_w = 0
    if show_line_numbers:
        sample = "0" * (len(str(len(lines))) + 1)
        ln_w = int(_text_w(sample, font)) + _PAD

    # Max content width
    max_content_w = max(
        (sum(_text_w(txt, font) for _, txt in line) for line in lines),
        default=0,
    )

    width = int(max_content_w) + ln_w + label_w + 2 * _PAD
    height = lh * len(lines) + 2 * _PAD

    img = Image.new("RGB", (max(width, 120, min_width), max(height, lh + _PAD)), color=bg)
    draw = ImageDraw.Draw(img)

    # Draw left margin label
    if left_margin_label and label_font:
        brightness = sum(bg) / 3
        label_color = _shift(bg, 45 if brightness < 128 else -45)
        label_lh = _line_height(label_font, gap=0)
        label_y = _PAD + (lh - label_lh) // 2  # vertically aligned with first text line
        draw.text((_PAD // 4, label_y), left_margin_label,
                  font=label_font, fill=label_color)

    # Line-number gutter
    if show_line_numbers and ln_w:
        gutter_bg = _shift(bg, -18)
        draw.rectangle([label_w, 0, label_w + ln_w, img.height], fill=gutter_bg)
        draw.line([(label_w + ln_w, 0), (label_w + ln_w, img.height)],
                  fill=_shift(bg, -30), width=1)

    for i, line in enumerate(lines):
        y = _PAD + i * lh

        if show_line_numbers:
            num_str = str(i + 1)
            nx = label_w + ln_w - int(_text_w(num_str, font)) - 4
            draw.text((max(nx, 2), y), num_str, font=font, fill=(110, 110, 110))

        x = _PAD + ln_w + label_w
        for color, text in line:
            if text:
                draw.text((x, y), text, font=font, fill=color)
                x += int(_text_w(text, font))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _tokenize(
    source: str, language: str, style_cls
) -> list[list[tuple[tuple[int, int, int], str]]]:
    """Tokenize code into per-line colored segments for rendering.

    Args:
        source: Source code or plain text to tokenize.
        language: Language hint used to choose a lexer.
        style_cls: Pygments style used to resolve token colors.

    Returns:
        Per-line token segments as ``[(color_rgb, text), ...]`` lists.
    """
    try:
        lexer = get_lexer_by_name(language)
    except Exception:
        try:
            lexer = guess_lexer(source)
        except Exception:
            lexer = TextLexer()

    default_color = _default_fg(style_cls)
    lines: list = [[]]

    for ttype, value in lex(source, lexer):
        info = style_cls.style_for_token(ttype)
        color = _hex_to_rgb(info["color"]) if info.get("color") else default_color

        parts = value.split("\n")
        for k, part in enumerate(parts):
            if k > 0:
                lines.append([])
            if part:
                lines[-1].append((color, part))

    # Drop trailing empty line that Pygments often appends
    while lines and not lines[-1]:
        lines.pop()

    return lines or [[]]


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=32)
def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a monospace font at the requested size.

    Args:
        size: Requested font size in pixels.

    Returns:
        A Pillow font object suitable for code rendering.
    """
    path = _find_font()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    # Pillow >=10 supports a `size` argument on load_default.
    try:
        params = inspect.signature(ImageFont.load_default).parameters
    except (TypeError, ValueError):
        params = {}
    if "size" in params:
        return ImageFont.load_default(size=size)
    return ImageFont.load_default()


@lru_cache(maxsize=1)
def _find_font() -> Optional[str]:
    """Return the first available monospace font path for the platform.

    Args:
        None.

    Returns:
        A filesystem path string, or ``None`` when no candidate exists.
    """
    platform = sys.platform
    if platform.startswith("linux"):
        candidates = _FONT_CANDIDATES["linux"]
    elif platform == "darwin":
        candidates = _FONT_CANDIDATES["darwin"]
    else:
        candidates = _FONT_CANDIDATES["win32"]

    for path in candidates:
        if Path(path).exists():
            return path
    return None


# ---------------------------------------------------------------------------
# Measurement helpers
# ---------------------------------------------------------------------------

def _text_w(text: str, font) -> float:
    """Measure the rendered width of text using a given font.

    Args:
        text: Text string to measure.
        font: Font object used for measurement.

    Returns:
        Approximate rendered width of the text in pixels.
    """
    try:
        return font.getlength(text)
    except AttributeError:
        try:
            bbox = font.getbbox(text)
            return float(bbox[2] - bbox[0])
        except Exception:
            return float(len(text) * 8)


def _line_height(font, gap: int = _LINE_GAP) -> int:
    """Measure the height of one rendered line for a font.

    Args:
        font: Font object used for measurement.
        gap: Extra vertical spacing to add between lines.

    Returns:
        Pixel height for one rendered line.
    """
    try:
        asc, desc = font.getmetrics()
        return asc + desc + gap
    except Exception:
        return getattr(font, "size", 14) + gap


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a hex color string to an RGB tuple.

    Args:
        hex_color: Hex color string such as ``#ff00aa``.

    Returns:
        A three-tuple of red, green, and blue values.
    """
    h = (hex_color or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return (200, 200, 200)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _shift(rgb: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    """Brighten or darken an RGB tuple by a fixed amount.

    Args:
        rgb: Source RGB color tuple.
        amount: Signed adjustment applied to each channel.

    Returns:
        A shifted RGB color tuple clamped to valid channel bounds.
    """
    return tuple(max(0, min(255, c + amount)) for c in rgb)


def _default_fg(style_cls) -> tuple[int, int, int]:
    """Determine the default foreground color for a Pygments style.

    Args:
        style_cls: Pygments style used to inspect text colors.

    Returns:
        Default foreground color as an RGB tuple.
    """
    for ttype in (Token.Text, Token):
        info = style_cls.style_for_token(ttype)
        if info.get("color"):
            return _hex_to_rgb(info["color"])
    # Infer from background brightness
    bg = _hex_to_rgb(style_cls.background_color)
    return (220, 220, 220) if sum(bg) / 3 < 128 else (40, 40, 40)


class _OutputStyle:
    """Lighter, muted Pygments-like style used for output cells."""

    def __init__(self, base) -> None:
        """Derive a muted output-cell palette from a Pygments style.

        Args:
            base: Base Pygments style object to soften for outputs.

        Returns:
            ``None``. The instance stores the base style and new background.
        """
        self._base = base
        base_bg = _hex_to_rgb(base.background_color)
        shift = 25 if sum(base_bg) / 3 < 128 else 20
        self.background_color = _rgb_to_hex(_shift(base_bg, shift))

    def style_for_token(self, ttype):
        """Return a muted token style mapping for output rendering.

        Args:
            ttype: Pygments token type to style.

        Returns:
            A style mapping for the token type.
        """
        info = self._base.style_for_token(ttype)
        if not info.get("color"):
            return info
        rgb = _hex_to_rgb(info["color"])
        gray = sum(rgb) // 3
        muted = tuple(int(c * 0.6 + gray * 0.4) for c in rgb)
        return {"color": _rgb_to_hex(muted)}


def _create_output_style(base_style):
    """Create a lighter muted style for output-cell rendering.

    Args:
        base_style: Base Pygments style used for code rendering.

    Returns:
        A muted style wrapper used for output blocks.
    """
    return _OutputStyle(base_style)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert an RGB tuple to a hex color string.

    Args:
        rgb: Source RGB color tuple.

    Returns:
        Hex color string beginning with ``#``.
    """
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


@lru_cache(maxsize=16)
def _style_for_theme(theme: str):
    """Return a cached Pygments style class for a theme name.

    Args:
        theme: Pygments theme name to resolve.

    Returns:
        The Pygments style class for the theme.
    """
    return get_style_by_name(theme)
