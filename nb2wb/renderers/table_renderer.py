"""Render HTML tables to PNG data URIs for editor-compatible publishing."""
from __future__ import annotations

import base64
import inspect
import io
import re
import sys
import warnings
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..config import TableConfig
from ._image_utils import round_corners as _round_corners

_TABLE_RE = re.compile(r"<table\b[^>]*>.*?</table>", re.IGNORECASE | re.DOTALL)
_ALIGN_RE = re.compile(r"text-align\s*:\s*(left|center|right)", re.IGNORECASE)
_SPACE_RE = re.compile(r"[ \t\r\f\v]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")

_FONT_CANDIDATES: dict[str, list[str]] = {
    "linux": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ],
    "darwin": [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
    "win32": [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
}

_LINE_GAP = 4
_MIN_COL_WIDTH = 64


@dataclass
class _Cell:
    text: str
    align: str
    is_header: bool


class _TableParser(HTMLParser):
    """Extract simple table rows/cells from HTML output."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[_Cell]] = []
        self._thead_depth = 0
        self._current_row: list[_Cell] | None = None
        self._current_cell: _Cell | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()

        if name == "thead":
            self._thead_depth += 1
            return

        if name == "tr":
            self._current_row = []
            return

        if name in {"th", "td"} and self._current_row is not None:
            attrs_map = {k.lower(): (v or "") for k, v in attrs if k}
            align = _extract_align(attrs_map)
            self._current_cell = _Cell(
                text="",
                align=align,
                is_header=name == "th" or self._thead_depth > 0,
            )
            self._chunks = []
            return

        if self._current_cell is None:
            return

        if name == "br":
            self._chunks.append("\n")
        elif name in {"p", "div"}:
            if self._chunks and not self._chunks[-1].endswith("\n"):
                self._chunks.append("\n")
        elif name == "li":
            if self._chunks and not self._chunks[-1].endswith("\n"):
                self._chunks.append("\n")
            self._chunks.append("- ")

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()

        if name == "thead" and self._thead_depth:
            self._thead_depth -= 1
            return

        if name in {"th", "td"} and self._current_row is not None and self._current_cell is not None:
            self._current_cell.text = _normalize_cell_text("".join(self._chunks))
            self._current_row.append(self._current_cell)
            self._current_cell = None
            self._chunks = []
            return

        if name == "tr" and self._current_row is not None:
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None
            return

        if self._current_cell is not None and name in {"p", "div"}:
            if self._chunks and not self._chunks[-1].endswith("\n"):
                self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._chunks.append(data)


def render_tables_as_images(html: str, config: TableConfig) -> str:
    """Replace each HTML ``<table>`` fragment with an equivalent PNG ``<img>``."""

    def _replace(match: re.Match[str]) -> str:
        table_html = match.group(0)
        try:
            uri = render_table_html(table_html, config)
        except Exception as exc:  # pragma: no cover - fallback path
            warnings.warn(
                f"Table render failed; keeping native HTML table: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            return table_html
        return f'<img src="{uri}" alt="table">'

    return _TABLE_RE.sub(_replace, html)


def render_table_html(table_html: str, config: TableConfig) -> str:
    """Render one HTML table fragment to a PNG data URI."""
    rows = _parse_rows(table_html)
    if not rows:
        raise ValueError("No table rows found.")

    col_count = max(len(row) for row in rows)
    rows = [row + [_Cell(text="", align="left", is_header=False)] * (col_count - len(row)) for row in rows]

    border_w = max(1, int(config.border_width))
    font = _load_font(config.font, config.font_size)
    dummy = Image.new("RGB", (16, 16), config.background)
    measure = ImageDraw.Draw(dummy)

    col_widths = _initial_col_widths(rows, col_count, config, measure, font)
    target_inner = max(
        config.image_width - (col_count + 1) * border_w,
        col_count * (_MIN_COL_WIDTH + 2 * config.cell_padding_x),
    )
    col_widths = _fit_col_widths(col_widths, target_inner, _MIN_COL_WIDTH + 2 * config.cell_padding_x)

    line_h = _line_height(font)
    wrapped_rows: list[list[list[str]]] = []
    row_heights: list[int] = []
    for row in rows:
        wrapped_row: list[list[str]] = []
        row_h = 0
        for idx, cell in enumerate(row):
            inner_w = max(1, col_widths[idx] - 2 * config.cell_padding_x)
            lines = _wrap_text(cell.text, inner_w, measure, font)
            wrapped_row.append(lines)
            cell_h = max(line_h, len(lines) * line_h) + 2 * config.cell_padding_y
            row_h = max(row_h, cell_h)
        wrapped_rows.append(wrapped_row)
        row_heights.append(row_h)

    table_w = sum(col_widths) + (col_count + 1) * border_w
    table_h = sum(row_heights) + (len(rows) + 1) * border_w

    canvas_w = max(config.image_width, table_w)
    canvas = Image.new("RGB", (canvas_w, table_h), config.background)
    draw = ImageDraw.Draw(canvas)

    table_x = (canvas_w - table_w) // 2
    _draw_cells(
        draw,
        rows,
        wrapped_rows,
        row_heights,
        col_widths,
        table_x=table_x,
        border_width=border_w,
        config=config,
        font=font,
        line_height=line_h,
    )
    _draw_grid(
        draw,
        row_heights,
        col_widths,
        table_x=table_x,
        table_height=table_h,
        border_width=border_w,
        border_color=config.border_color,
    )

    if config.border_radius:
        canvas = _round_corners(canvas, config.border_radius)

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    payload = base64.b64encode(out.getvalue()).decode("ascii")
    return f"data:image/png;base64,{payload}"


def _parse_rows(table_html: str) -> list[list[_Cell]]:
    parser = _TableParser()
    parser.feed(table_html)
    parser.close()
    return parser.rows


def _extract_align(attrs: dict[str, str]) -> str:
    align = attrs.get("align", "").strip().lower()
    if align in {"left", "center", "right"}:
        return align

    style = attrs.get("style", "")
    match = _ALIGN_RE.search(style)
    if match:
        return match.group(1).lower()
    return "left"


def _normalize_cell_text(text: str) -> str:
    normalized = text.replace("\xa0", " ")
    normalized = _SPACE_RE.sub(" ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    normalized = _MULTI_NL_RE.sub("\n\n", normalized)
    return normalized.strip()


def _initial_col_widths(
    rows: list[list[_Cell]],
    col_count: int,
    config: TableConfig,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
) -> list[int]:
    widths = [_MIN_COL_WIDTH + 2 * config.cell_padding_x for _ in range(col_count)]
    for row in rows:
        for idx, cell in enumerate(row):
            width = _max_line_width(cell.text.splitlines() or [cell.text], draw, font)
            widths[idx] = max(widths[idx], int(width) + 2 * config.cell_padding_x)
    return widths


def _fit_col_widths(widths: list[int], target: int, minimum: int) -> list[int]:
    if not widths:
        return widths

    fitted = [max(minimum, int(w)) for w in widths]
    total = sum(fitted)
    if total == target:
        return fitted

    if total < target:
        extra = target - total
        idx = 0
        while extra > 0:
            col = idx % len(fitted)
            fitted[col] += 1
            idx += 1
            extra -= 1
        return fitted

    scale = target / total
    fitted = [max(minimum, int(w * scale)) for w in fitted]
    total = sum(fitted)

    if total > target:
        overshoot = total - target
        order = sorted(range(len(fitted)), key=lambda i: fitted[i], reverse=True)
        idx = 0
        limit = len(order) * max(target, 1) * 2
        while overshoot > 0 and idx < limit:
            col = order[idx % len(order)]
            if fitted[col] > minimum:
                fitted[col] -= 1
                overshoot -= 1
            idx += 1
    elif total < target:
        deficit = target - total
        idx = 0
        while deficit > 0:
            col = idx % len(fitted)
            fitted[col] += 1
            idx += 1
            deficit -= 1

    return fitted


def _wrap_text(
    text: str,
    max_width: int,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
) -> list[str]:
    if not text:
        return [""]

    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append("")
            continue

        words = paragraph.split(" ")
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if _text_width(candidate, draw, font) <= max_width:
                current = candidate
                continue

            if _text_width(word, draw, font) > max_width:
                lines.append(current)
                for piece in _break_long_word(word, max_width, draw, font):
                    lines.append(piece)
                current = ""
                continue

            lines.append(current)
            current = word

        if current:
            lines.append(current)

    return lines or [""]


def _break_long_word(
    token: str,
    max_width: int,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
) -> list[str]:
    if not token:
        return [""]

    parts: list[str] = []
    chunk = ""
    for char in token:
        candidate = chunk + char
        if chunk and _text_width(candidate, draw, font) > max_width:
            parts.append(chunk)
            chunk = char
        else:
            chunk = candidate
    if chunk:
        parts.append(chunk)
    return parts or [token]


def _draw_cells(
    draw: ImageDraw.ImageDraw,
    rows: list[list[_Cell]],
    wrapped_rows: list[list[list[str]]],
    row_heights: list[int],
    col_widths: list[int],
    *,
    table_x: int,
    border_width: int,
    config: TableConfig,
    font: ImageFont.ImageFont,
    line_height: int,
) -> None:
    y = border_width
    for row_idx, row in enumerate(rows):
        x = table_x + border_width
        row_h = row_heights[row_idx]
        for col_idx, cell in enumerate(row):
            cell_w = col_widths[col_idx]
            fill = config.header_background if cell.is_header else config.background
            draw.rectangle(
                (x, y, x + cell_w - 1, y + row_h - 1),
                fill=fill,
            )
            text_color = config.header_color if cell.is_header else config.color
            _draw_cell_text(
                draw,
                wrapped_rows[row_idx][col_idx],
                x,
                y,
                cell_w,
                row_h,
                align=cell.align,
                color=text_color,
                font=font,
                line_height=line_height,
                pad_x=config.cell_padding_x,
            )
            x += cell_w + border_width
        y += row_h + border_width


def _draw_grid(
    draw: ImageDraw.ImageDraw,
    row_heights: list[int],
    col_widths: list[int],
    *,
    table_x: int,
    table_height: int,
    border_width: int,
    border_color: str,
) -> None:
    x = table_x
    for idx in range(len(col_widths) + 1):
        draw.rectangle(
            (x, 0, x + border_width - 1, table_height - 1),
            fill=border_color,
        )
        if idx < len(col_widths):
            x += col_widths[idx] + border_width

    y = 0
    table_width = sum(col_widths) + (len(col_widths) + 1) * border_width
    for idx in range(len(row_heights) + 1):
        draw.rectangle(
            (table_x, y, table_x + table_width - 1, y + border_width - 1),
            fill=border_color,
        )
        if idx < len(row_heights):
            y += row_heights[idx] + border_width


def _draw_cell_text(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    align: str,
    color: str,
    font: ImageFont.ImageFont,
    line_height: int,
    pad_x: int,
) -> None:
    if not lines:
        return

    total_text_h = len(lines) * line_height
    text_y = y + max((height - total_text_h) // 2, 0)
    inner_w = max(1, width - 2 * pad_x)

    for line in lines:
        line_w = _text_width(line, draw, font)
        if align == "center":
            text_x = x + pad_x + max((inner_w - line_w) / 2, 0)
        elif align == "right":
            text_x = x + width - pad_x - line_w
        else:
            text_x = x + pad_x
        draw.text((text_x, text_y), line, font=font, fill=color)
        text_y += line_height


def _max_line_width(lines: list[str], draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> float:
    return max((_text_width(line, draw, font) for line in lines), default=0.0)


def _line_height(font: ImageFont.ImageFont) -> int:
    try:
        asc, desc = font.getmetrics()
        return asc + desc + _LINE_GAP
    except Exception:
        return getattr(font, "size", 14) + _LINE_GAP


def _text_width(text: str, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> float:
    try:
        return float(draw.textlength(text, font=font))
    except Exception:
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            return float(bbox[2] - bbox[0])
        except Exception:
            return float(len(text) * max(getattr(font, "size", 12) // 2, 6))


def _load_font(preferred_font: str, size: int) -> ImageFont.ImageFont:
    path = Path(preferred_font)
    if path.exists():
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            pass

    try:
        return ImageFont.truetype(preferred_font, size)
    except Exception:
        pass

    for candidate in _candidate_fonts():
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue

    try:
        params = inspect.signature(ImageFont.load_default).parameters
    except (TypeError, ValueError):
        params = {}
    if "size" in params:
        return ImageFont.load_default(size=size)
    return ImageFont.load_default()


def _candidate_fonts() -> list[str]:
    platform = sys.platform
    if platform.startswith("linux"):
        return _FONT_CANDIDATES["linux"]
    if platform == "darwin":
        return _FONT_CANDIDATES["darwin"]
    return _FONT_CANDIDATES["win32"]
