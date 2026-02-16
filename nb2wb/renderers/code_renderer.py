"""
Render source code and plain-text output to PNG images using PIL + Pygments.

Each image is returned as raw PNG bytes; callers base64-encode them for
embedding in HTML.
"""
from __future__ import annotations

import io
import sys
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_code(source: str, language: str, config: CodeConfig, *,
                apply_padding: bool = True,
                execution_count: Optional[int] = None) -> bytes:
    """Render *source* with syntax highlighting to PNG bytes."""
    font = _load_font(config.font_size)
    style_cls = get_style_by_name(config.theme)
    lines = _tokenize(source, language, style_cls)
    png = _paint(lines, font, style_cls, show_line_numbers=config.line_numbers,
                 min_width=config.image_width)

    if apply_padding:
        # Standalone rendering: draw footer, border, and padding now.
        ec_text = f"[{execution_count}]" if execution_count is not None else "[ ]"
        lang_display = language.capitalize() if language else ""
        png = _draw_footer(png, style_cls, config, left_text=ec_text,
                           right_text=lang_display)
        png = _draw_border(png, style_cls)
        if config.padding_x or config.padding_y:
            bg = config.background or style_cls.background_color
            png = _outer_pad(png, config.padding_x, config.padding_y, bg)
    # When apply_padding is False the caller is expected to stack this image
    # via vstack_and_pad which draws footer, border, and padding *after*
    # normalising widths so that everything spans the full combined width.
    return png


def render_output_text(text: str, config: CodeConfig, *,
                       apply_padding: bool = True) -> bytes:
    """Render plain-text output (stdout, repr, error) to PNG bytes with lighter styling."""
    font = _load_font(config.font_size)
    style_cls = get_style_by_name(config.theme)
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
    """
    style_cls = get_style_by_name(config.theme)
    output_bg = _create_output_style(style_cls).background_color
    sep_color = config.background or output_bg
    has_footer = bool(code_footer_left or code_footer_right)

    if len(png_list) == 1:
        png = png_list[0]
        if has_footer:
            png = _draw_footer(png, style_cls, config,
                               left_text=code_footer_left,
                               right_text=code_footer_right)
        if draw_code_border:
            png = _draw_border(png, style_cls)
    else:
        imgs = [Image.open(io.BytesIO(b)).convert("RGB") for b in png_list]
        w = max(img.width for img in imgs)

        # Normalise widths ------------------------------------------------
        for idx in range(len(imgs)):
            if imgs[idx].width < w:
                img = imgs[idx]
                # Replicate the rightmost column so every horizontal
                # band extends to the full width with the correct colour.
                right_col = img.crop((img.width - 1, 0, img.width, img.height))
                fill = right_col.resize((w - img.width, img.height), Image.NEAREST)
                extended = Image.new("RGB", (w, img.height))
                extended.paste(img, (0, 0))
                extended.paste(fill, (img.width, 0))
                imgs[idx] = extended

        # Draw footer on code image at the normalised width ---------------
        if has_footer:
            buf = io.BytesIO()
            imgs[0].save(buf, format="PNG")
            footer_png = _draw_footer(buf.getvalue(), style_cls, config,
                                      left_text=code_footer_left,
                                      right_text=code_footer_right)
            imgs[0] = Image.open(io.BytesIO(footer_png)).convert("RGB")

        # Combine ----------------------------------------------------------
        sep = config.separator
        h = sum(img.height for img in imgs) + sep * (len(imgs) - 1)
        combined = Image.new("RGB", (w, h), _hex_to_rgb(sep_color))
        y = 0
        for i, img in enumerate(imgs):
            combined.paste(img, (0, y))
            y += img.height
            if i < len(imgs) - 1:
                y += sep

        # Draw border on the code cell region after width normalisation
        if draw_code_border:
            first_h = imgs[0].height
            draw = ImageDraw.Draw(combined)
            bg = _hex_to_rgb(style_cls.background_color)
            brightness = sum(bg) / 3
            border_color = _shift(bg, 40 if brightness < 128 else -40)
            draw.rectangle([0, 0, w - 1, first_h - 1],
                           outline=border_color, width=1)

        buf = io.BytesIO()
        combined.save(buf, format="PNG")
        png = buf.getvalue()
    if config.padding_x or config.padding_y:
        png = _outer_pad(png, config.padding_x, config.padding_y, sep_color)
    if config.border_radius:
        img = Image.open(io.BytesIO(png)).convert("RGB")
        img = _round_corners(img, config.border_radius)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png = buf.getvalue()
    return png


# ---------------------------------------------------------------------------
# Rendering internals
# ---------------------------------------------------------------------------


def _outer_pad(png_bytes: bytes, padding_x: int, padding_y: int, background: str) -> bytes:
    """Wrap a PNG image with outer padding of the given background colour."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    canvas = Image.new(
        "RGB",
        (img.width + 2 * padding_x, img.height + 2 * padding_y),
        background,
    )
    canvas.paste(img, (padding_x, padding_y))
    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


def _draw_footer(png_bytes: bytes, style_cls, config: CodeConfig, *,
                 left_text: str, right_text: str) -> bytes:
    """Append a Jupyter-style footer bar to a code cell image."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    bg = _hex_to_rgb(style_cls.background_color)
    footer_bg = _shift(bg, -12)

    footer_font = _load_font(max(int(config.font_size * _FOOTER_FONT_RATIO), 12))
    footer_lh = _line_height(footer_font, gap=0)
    footer_h = footer_lh + _PAD
    line_color = _shift(bg, -25)
    text_color = _shift(bg, 50 if sum(bg) / 3 < 128 else -50)

    # New canvas: original image + 1px separator + footer
    new_h = img.height + 1 + footer_h
    canvas = Image.new("RGB", (img.width, new_h), footer_bg)
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)

    # Separator line at bottom of code area
    draw.line([(0, img.height), (img.width, img.height)],
              fill=line_color, width=1)

    # Footer text
    text_y = img.height + 1 + (footer_h - footer_lh) // 2
    draw.text((_PAD, text_y), left_text, font=footer_font, fill=text_color)
    right_w = int(_text_w(right_text, footer_font))
    draw.text((img.width - right_w - _PAD, text_y), right_text,
              font=footer_font, fill=text_color)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def _draw_border(png_bytes: bytes, style_cls) -> bytes:
    """Draw a thin border rectangle around the code cell image."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    bg = _hex_to_rgb(style_cls.background_color)
    brightness = sum(bg) / 3
    border_color = _shift(bg, 40 if brightness < 128 else -40)
    draw.rectangle([0, 0, img.width - 1, img.height - 1],
                   outline=border_color, width=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _paint(
    lines: list[list[tuple[tuple[int, int, int], str]]],
    font: ImageFont.FreeTypeFont,
    style_cls,
    show_line_numbers: bool,
    min_width: int = 0,
    left_margin_label: Optional[str] = None,
) -> bytes:
    """Render tokenized lines onto a PIL image and return raw PNG bytes."""
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
    """Return per-line token lists: [ [(color_rgb, text), ...], ... ]"""
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

def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a monospace TrueType font at the given size, falling back to Pillow's default."""
    path = _find_font()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    # Pillow ≥10 supports a `size` argument on the default font
    try:
        return ImageFont.load_default(size=size)  # type: ignore[call-arg]
    except TypeError:
        return ImageFont.load_default()


def _find_font() -> Optional[str]:
    """Return the path to the first available monospace font for the current platform."""
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
    """Return the rendered width of *text* in pixels using the given font."""
    try:
        return font.getlength(text)
    except AttributeError:
        try:
            bbox = font.getbbox(text)
            return float(bbox[2] - bbox[0])
        except Exception:
            return float(len(text) * 8)


def _line_height(font, gap: int = _LINE_GAP) -> int:
    """Return the pixel height of a single text line (ascent + descent + gap)."""
    try:
        asc, desc = font.getmetrics()
        return asc + desc + gap
    except Exception:
        return getattr(font, "size", 14) + gap


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a hex color string (e.g. ``#ff00aa``) to an (R, G, B) tuple."""
    h = (hex_color or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return (200, 200, 200)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _shift(rgb: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    """Brighten (amount > 0) or darken (amount < 0) an RGB tuple."""
    return tuple(max(0, min(255, c + amount)) for c in rgb)  # type: ignore[return-value]


def _default_fg(style_cls) -> tuple[int, int, int]:
    """Determine the default foreground color from a Pygments style, inferring from background if needed."""
    for ttype in (Token.Text, Token):
        info = style_cls.style_for_token(ttype)
        if info.get("color"):
            return _hex_to_rgb(info["color"])
    # Infer from background brightness
    bg = _hex_to_rgb(style_cls.background_color)
    return (220, 220, 220) if sum(bg) / 3 < 128 else (40, 40, 40)


def _create_output_style(base_style):
    """Create a lighter, muted style for output cells."""
    class OutputStyle:
        def __init__(self, base):
            self._base = base
            base_bg = _hex_to_rgb(base.background_color)
            # Lighten the background significantly
            if sum(base_bg) / 3 < 128:  # Dark theme
                self.background_color = _rgb_to_hex(_shift(base_bg, 25))
            else:  # Light theme
                self.background_color = _rgb_to_hex(_shift(base_bg, 20))

        def style_for_token(self, ttype):
            info = self._base.style_for_token(ttype)
            # Make text more muted/grayed
            if info.get("color"):
                rgb = _hex_to_rgb(info["color"])
                base_bg = _hex_to_rgb(self._base.background_color)
                # Move color 40% towards gray
                gray = sum(rgb) // 3
                muted = tuple(int(c * 0.6 + gray * 0.4) for c in rgb)
                return {"color": _rgb_to_hex(muted)}
            return info

    return OutputStyle(base_style)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex color string."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
