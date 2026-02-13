"""
Render display-math LaTeX blocks to base64-encoded PNG data URIs.

Strategy
--------
1. Try matplotlib with usetex=True (requires a LaTeX installation + dvipng/dvisvgm).
2. Fall back to matplotlib's built-in mathtext renderer (no LaTeX needed,
   supports a large subset of LaTeX).
"""
from __future__ import annotations

import base64
import io
import re
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageChops

from ..config import LatexConfig

# ---------------------------------------------------------------------------
# Patterns that identify display-math spans
# ---------------------------------------------------------------------------
_PATTERNS = [
    # $$...$$
    re.compile(r"\$\$(.*?)\$\$", re.DOTALL),
    # \[...\]
    re.compile(r"\\\[(.*?)\\\]", re.DOTALL),
    # \begin{equation|align|gather|multline|eqnarray}[*]...\end{...}[*]
    re.compile(
        r"\\begin\{(equation|align|gather|multline|eqnarray)(\*)?\}"
        r"(.*?)"
        r"\\end\{\1\2?\}",
        re.DOTALL,
    ),
]


def extract_display_math(text: str) -> list[tuple[int, int, str]]:
    """
    Return a list of (start, end, latex_content) for every display-math
    block found in *text*, sorted by position, non-overlapping.
    """
    raw: list[tuple[int, int, str]] = []

    for m in re.finditer(r"\$\$(.*?)\$\$", text, re.DOTALL):
        raw.append((m.start(), m.end(), m.group(1).strip()))

    for m in re.finditer(r"\\\[(.*?)\\\]", text, re.DOTALL):
        raw.append((m.start(), m.end(), m.group(1).strip()))

    for m in re.finditer(
        r"\\begin\{(equation|align|gather|multline|eqnarray)(\*)?\}"
        r"(.*?)"
        r"\\end\{\1\2?\}",
        text,
        re.DOTALL,
    ):
        raw.append((m.start(), m.end(), m.group(3).strip()))

    # Sort and remove overlaps
    raw.sort(key=lambda x: x[0])
    result: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, latex in raw:
        if start >= last_end:
            result.append((start, end, latex))
            last_end = end

    return result


def render_latex_block(latex: str, config: LatexConfig) -> str:
    """
    Render a display-math LaTeX string and return a ``data:image/png;base64,...``
    URI that can be used directly in an ``<img src="...">`` tag.
    """
    if config.try_usetex:
        try:
            return _render_usetex(latex, config)
        except Exception:
            pass  # fall through to mathtext

    return _render_mathtext(latex, config)


# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------

def _trim_and_pad(png_bytes: bytes, config: LatexConfig) -> bytes:
    """Trim background whitespace, add vertical padding, and center on a fixed-width canvas."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    bg = Image.new("RGB", img.size, config.background)
    bbox = ImageChops.difference(img, bg).getbbox()
    if bbox:
        img = img.crop(bbox)
    pad_px = config.padding
    canvas = Image.new(
        "RGB",
        (config.image_width, img.height + 2 * pad_px),
        config.background,
    )
    canvas.paste(img, ((config.image_width - img.width) // 2, pad_px))
    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


# ---------------------------------------------------------------------------
# Rendering back-ends
# ---------------------------------------------------------------------------

def _render_mathtext(latex: str, config: LatexConfig) -> str:
    """Use matplotlib's built-in mathtext (no LaTeX installation required)."""
    expr = f"${latex}$"

    fig = plt.figure(dpi=config.dpi)
    fig.patch.set_facecolor(config.background)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.patch.set_facecolor(config.background)

    try:
        ax.text(
            0.5,
            0.5,
            expr,
            fontsize=config.font_size,
            color=config.color,
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=config.dpi,
            bbox_inches="tight",
            pad_inches=0,
            facecolor=config.background,
        )
        buf.seek(0)
        data = base64.b64encode(_trim_and_pad(buf.read(), config)).decode("ascii")
        return f"data:image/png;base64,{data}"
    finally:
        plt.close(fig)


def _render_usetex(latex: str, config: LatexConfig) -> str:
    """Use a full LaTeX installation via matplotlib's usetex mode."""
    prev_usetex = plt.rcParams.get("text.usetex", False)
    prev_preamble = plt.rcParams.get("text.latex.preamble", "")

    plt.rcParams["text.usetex"] = True
    plt.rcParams["text.latex.preamble"] = (
        r"\usepackage{amsmath}" r"\usepackage{amssymb}" r"\usepackage{bm}"
    )

    expr = rf"\[{latex}\]"

    fig = plt.figure(dpi=config.dpi)
    fig.patch.set_facecolor(config.background)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.patch.set_facecolor(config.background)

    try:
        ax.text(
            0.5,
            0.5,
            expr,
            fontsize=config.font_size,
            color=config.color,
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=config.dpi,
            bbox_inches="tight",
            pad_inches=0,
            facecolor=config.background,
        )
        buf.seek(0)
        data = base64.b64encode(_trim_and_pad(buf.read(), config)).decode("ascii")
        return f"data:image/png;base64,{data}"
    finally:
        plt.close(fig)
        plt.rcParams["text.usetex"] = prev_usetex
        plt.rcParams["text.latex.preamble"] = prev_preamble
