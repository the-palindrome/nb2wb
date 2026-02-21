"""
Render display-math LaTeX blocks to base64-encoded PNG data URIs.

Strategy
--------
1. Try a direct latex + dvipng subprocess pipeline (requires a LaTeX installation
   and dvipng).  This preserves DVI color specials so \\color{} commands in
   formulas render correctly.
2. Fall back to matplotlib's built-in mathtext renderer (no LaTeX needed,
   supports a large subset of LaTeX, but ignores color commands).
"""
from __future__ import annotations

import base64
import io
import re
import subprocess
import tempfile
from pathlib import Path as _Path
from typing import Optional

import matplotlib
import matplotlib.colors as mcolors

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageChops, ImageDraw, ImageFont

from ..config import LatexConfig
from ._image_utils import round_corners as _round_corners

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TEX_COMMAND_RE = re.compile(r"(?<!\\)\\([A-Za-z@]+)\*?")
_PACKAGE_RE = re.compile(
    r"(?<!\\)\\(?:usepackage|RequirePackage)(?:\[[^\]]*\])?\{([^}]*)\}",
    re.IGNORECASE,
)
_FORBIDDEN_TEX_COMMANDS = frozenset(
    {
        "input",
        "@@input",
        "include",
        "csname",
        "endcsname",
        "expandafter",
        "scantokens",
        "openin",
        "openout",
        "closein",
        "closeout",
        "read",
        "write",
        "write18",
        "immediate",
        "special",
        "catcode",
        "newread",
        "newwrite",
    }
)
_FORBIDDEN_PACKAGES = frozenset(
    {
        "shellesc",
        "catchfile",
        "catchfilebetweentags",
        "verbatim",
    }
)
_MAX_LATEX_CHARS = 10_000
_MAX_PREAMBLE_CHARS = 20_000


def _strip_tex_comments(text: str) -> str:
    """Drop unescaped LaTeX comments so validators inspect executable tokens."""
    return re.sub(r"(?<!\\)%[^\n]*", "", text)

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
        # Keep the full \begin{...}...\end{...} block so the renderer can
        # reconstruct the correct environment (not wrap it in \[...\]).
        raw.append((m.start(), m.end(), m.group(0).strip()))

    # Sort and remove overlaps
    raw.sort(key=lambda x: x[0])
    result: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, latex in raw:
        if start >= last_end:
            result.append((start, end, latex))
            last_end = end

    return result


def render_latex_block(
    latex: str, config: LatexConfig, preamble: str = "", tag: int | None = None
) -> str:
    """
    Render a display-math LaTeX string and return a ``data:image/png;base64,...``
    URI that can be used directly in an ``<img src="...">`` tag.

    *preamble* is extra LaTeX preamble collected from the notebook (via
    ``latex-preamble`` tagged cells).  It is concatenated with
    ``config.preamble`` and the built-in preamble when using usetex.

    *tag*, if given, is drawn as ``(N)`` at the right edge of the canvas.
    """
    combined_preamble = "\n".join(filter(None, [config.preamble, preamble]))

    if config.try_usetex:
        try:
            _validate_usetex_inputs(latex, combined_preamble)
            return _render_usetex(latex, config, combined_preamble, tag=tag)
        except Exception:
            pass  # fall through to mathtext

    return _render_mathtext(latex, config, tag=tag)


# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------


def _draw_tag(canvas: Image.Image, tag: int, config: LatexConfig) -> None:
    """Draw the equation number (N) at the right edge of the canvas, vertically centered."""
    draw = ImageDraw.Draw(canvas)
    text = f"({tag})"

    # Font: Computer Modern Roman from matplotlib's bundled fonts — matches LaTeX
    font_size_px = round(config.font_size / 72.27 * config.dpi)
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont
    font_dir = _Path(matplotlib.__file__).parent / "mpl-data" / "fonts" / "ttf"
    try:
        font = ImageFont.truetype(str(font_dir / "cmr10.ttf"), font_size_px)
    except (IOError, OSError):
        try:
            font = ImageFont.truetype(str(font_dir / "DejaVuSans.ttf"), font_size_px)
        except (IOError, OSError):
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    x = canvas.width - text_w - config.padding
    y = (canvas.height - text_h) // 2

    r, g, b = (round(c * 255) for c in mcolors.to_rgb(config.color))
    draw.text((x, y), text, font=font, fill=(r, g, b))


def _trim_and_pad(png_bytes: bytes, config: LatexConfig, tag: int | None = None) -> bytes:
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
    if tag is not None:
        _draw_tag(canvas, tag, config)
    if config.border_radius:
        canvas = _round_corners(canvas, config.border_radius)
    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


# ---------------------------------------------------------------------------
# Rendering back-ends
# ---------------------------------------------------------------------------

def _render_mathtext(latex: str, config: LatexConfig, tag: int | None = None) -> str:
    """Use matplotlib's built-in mathtext (no LaTeX installation required)."""
    if latex.lstrip().startswith(r"\begin{"):
        # mathtext has no multi-line environment support: strip tags and join rows
        inner = re.sub(r"\\(?:begin|end)\{[^}]+\}", "", latex)
        inner = re.sub(r"&", "", inner)
        rows = [r.strip() for r in re.split(r"\\\\(?:\[[^\]]*\])?", inner) if r.strip()]
        expr = "$" + r" \quad ".join(rows) + "$"
    else:
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
        data = base64.b64encode(_trim_and_pad(buf.read(), config, tag=tag)).decode("ascii")
        return f"data:image/png;base64,{data}"
    finally:
        plt.close(fig)


def _color_to_html(color: str) -> str:
    """Convert a matplotlib color spec to a 6-digit uppercase HTML hex (no '#')."""
    r, g, b = mcolors.to_rgb(color)
    return f"{round(r * 255):02X}{round(g * 255):02X}{round(b * 255):02X}"


def _color_to_dvipng(color: str) -> str:
    """Convert a matplotlib color spec to dvipng 'rgb R G B' format."""
    r, g, b = mcolors.to_rgb(color)
    return f"rgb {r:.6f} {g:.6f} {b:.6f}"


def _validate_usetex_inputs(latex: str, preamble: str) -> None:
    """Validate TeX inputs before invoking external LaTeX tooling."""
    if _CONTROL_CHAR_RE.search(latex) or _CONTROL_CHAR_RE.search(preamble):
        raise ValueError("Control characters are not allowed in LaTeX content.")
    if len(latex) > _MAX_LATEX_CHARS:
        raise ValueError(f"LaTeX expression exceeds {_MAX_LATEX_CHARS} characters.")
    if len(preamble) > _MAX_PREAMBLE_CHARS:
        raise ValueError(f"LaTeX preamble exceeds {_MAX_PREAMBLE_CHARS} characters.")

    normalized = _strip_tex_comments("\n".join([latex, preamble]))
    for command in _TEX_COMMAND_RE.findall(normalized):
        if command.lower() in _FORBIDDEN_TEX_COMMANDS:
            raise ValueError(f"Disallowed LaTeX command in usetex content: \\{command}")

    preamble_normalized = _strip_tex_comments(preamble)
    for match in _PACKAGE_RE.finditer(preamble_normalized):
        packages = [p.strip().lower() for p in match.group(1).split(",") if p.strip()]
        banned = sorted(pkg for pkg in packages if pkg in _FORBIDDEN_PACKAGES)
        if banned:
            raise ValueError(
                "Disallowed LaTeX package in preamble: " + ", ".join(banned)
            )


def _render_usetex(latex: str, config: LatexConfig, preamble: str = "", tag: int | None = None) -> str:
    """
    Direct latex + dvipng pipeline.

    Unlike matplotlib's usetex mode (which remaps all DVI colors to the text
    color before compositing), dvipng --truecolor renders DVI color specials
    faithfully, so \\color{} commands in formulas produce correctly colored output.
    """
    fg_html = _color_to_html(config.color)
    bg_html = _color_to_html(config.background)
    bg_dvipng = _color_to_dvipng(config.background)

    size = config.font_size
    baselineskip = round(size * 1.2)

    doc = "\n".join(filter(None, [
        r"\documentclass{article}",
        r"\usepackage{type1cm}",   # scalable CM fonts at any size
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{amsmath}",
        r"\usepackage{amssymb}",
        r"\usepackage{bm}",
        r"\usepackage{xcolor}",
        f"\\definecolor{{nbTextColor}}{{HTML}}{{{fg_html}}}",
        f"\\definecolor{{nbBgColor}}{{HTML}}{{{bg_html}}}",
        preamble,
        r"\pagecolor{nbBgColor}",
        r"\color{nbTextColor}",
        r"\pagestyle{empty}",
        r"\begin{document}",
        f"\\fontsize{{{size}}}{{{baselineskip}}}\\selectfont",
        latex if latex.lstrip().startswith(r"\begin{") else f"\\[{latex}\\]",
        r"\end{document}",
    ]))

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = _Path(tmpdir) / "formula.tex"
        dvi_path = _Path(tmpdir) / "formula.dvi"
        png_path = _Path(tmpdir) / "formula.png"

        tex_path.write_text(doc, encoding="utf-8")

        # Step 1: LaTeX → DVI
        result = subprocess.run(
            [
                "latex",
                "-interaction=nonstopmode",
                "-no-shell-escape",
                "-output-directory",
                tmpdir,
                str(tex_path),
            ],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            cwd=tmpdir,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"latex failed:\n{result.stdout.decode(errors='replace')}"
            )

        # Step 2: DVI → PNG  (--truecolor preserves xcolor specials)
        result = subprocess.run(
            ["dvipng", "--truecolor", f"-D{config.dpi}", "-T", "tight",
             "-bg", bg_dvipng, "-o", str(png_path), str(dvi_path)],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            cwd=tmpdir,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"dvipng failed:\n{result.stderr.decode(errors='replace')}"
            )

        png_bytes = png_path.read_bytes()

    data = base64.b64encode(_trim_and_pad(png_bytes, config, tag=tag)).decode("ascii")
    return f"data:image/png;base64,{data}"
