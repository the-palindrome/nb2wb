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
from collections import OrderedDict
from dataclasses import replace
from functools import lru_cache
from pathlib import Path as _Path
from threading import Lock

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
_MIN_EDGE_PADDING = 12
_MAX_EDGE_PADDING = 32
_MIN_AUTO_FONT_SIZE = 12

_LATEX_RENDER_CACHE: OrderedDict[tuple[object, ...], str] = OrderedDict()
_LATEX_RENDER_CACHE_LOCK = Lock()


@lru_cache(maxsize=1)
def _matplotlib_module():
    """Import matplotlib lazily and pin its backend to Agg.

    Args:
        None.

    Returns:
        The imported matplotlib module.
    """
    import matplotlib

    matplotlib.use("Agg", force=True)
    return matplotlib


@lru_cache(maxsize=1)
def _matplotlib_colors():
    """Import ``matplotlib.colors`` lazily.

    Args:
        None.

    Returns:
        The imported ``matplotlib.colors`` module.
    """
    import matplotlib.colors as mcolors

    return mcolors


@lru_cache(maxsize=1)
def _matplotlib_pyplot():
    """Import ``matplotlib.pyplot`` lazily.

    Args:
        None.

    Returns:
        The imported pyplot module configured for Agg rendering.
    """
    _matplotlib_module()
    import matplotlib.pyplot as plt

    return plt


def _strip_tex_comments(text: str) -> str:
    """Drop unescaped LaTeX comments from a source string.

    Args:
        text: LaTeX text that may contain comments.

    Returns:
        LaTeX text with executable comment content removed.
    """
    return re.sub(r"(?<!\\)%[^\n]*", "", text)

def extract_display_math(text: str) -> list[tuple[int, int, str]]:
    """
    Return a list of (start, end, latex_content) for every display-math
    block found in *text*, sorted by position, non-overlapping.

    Args:
        text: Source text that may contain display-math blocks.

    Returns:
        Non-overlapping display-math spans with extracted LaTeX content.
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


def _latex_cache_key(
    latex: str,
    config: LatexConfig,
    preamble: str,
    tag: int | None,
) -> tuple[object, ...]:
    """Build the cache key for one LaTeX render request.

    Args:
        latex: Display-math source being rendered.
        config: Active LaTeX rendering configuration.
        preamble: Combined LaTeX preamble text.
        tag: Optional equation number rendered beside the formula.

    Returns:
        A hashable tuple capturing all render-affecting inputs.
    """
    return (
        latex,
        preamble,
        tag,
        config.try_usetex,
        config.font_size,
        config.dpi,
        config.color,
        config.background,
        config.padding,
        config.image_width,
        config.preamble,
        config.border_radius,
    )


def _cache_get(key: tuple[object, ...]) -> str | None:
    """Fetch a cached render result and refresh its LRU position.

    Args:
        key: Cache key for the render request.

    Returns:
        The cached data URI, or ``None`` when no entry exists.
    """
    with _LATEX_RENDER_CACHE_LOCK:
        cached = _LATEX_RENDER_CACHE.get(key)
        if cached is not None:
            _LATEX_RENDER_CACHE.move_to_end(key)
        return cached


def _cache_set(key: tuple[object, ...], value: str, max_size: int) -> None:
    """Store a rendered formula in the bounded in-memory cache.

    Args:
        key: Cache key for the render request.
        value: Rendered PNG data URI to store.
        max_size: Maximum number of cached entries to retain.

    Returns:
        ``None``. The cache is updated in place.
    """
    if max_size <= 0:
        return
    with _LATEX_RENDER_CACHE_LOCK:
        _LATEX_RENDER_CACHE[key] = value
        _LATEX_RENDER_CACHE.move_to_end(key)
        while len(_LATEX_RENDER_CACHE) > max_size:
            _LATEX_RENDER_CACHE.popitem(last=False)


def _clear_render_cache() -> None:
    """Clear the in-memory LaTeX render cache.

    Args:
        None.

    Returns:
        ``None``. Cached render results are removed in place.
    """
    with _LATEX_RENDER_CACHE_LOCK:
        _LATEX_RENDER_CACHE.clear()


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

    Args:
        latex: Display-math LaTeX source to render.
        config: Active LaTeX rendering configuration.
        preamble: Extra notebook-derived LaTeX preamble text.
        tag: Optional equation number rendered beside the formula.

    Returns:
        A ``data:image/png`` URI containing the rendered formula.
    """
    combined_preamble = "\n".join(filter(None, [config.preamble, preamble]))
    cache_size = max(int(getattr(config, "cache_size", 0)), 0)
    cache_key: tuple[object, ...] | None = None

    if cache_size:
        cache_key = _latex_cache_key(latex, config, combined_preamble, tag)
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    if config.try_usetex:
        try:
            _validate_usetex_inputs(latex, combined_preamble)
            rendered = _render_usetex(latex, config, combined_preamble, tag=tag)
            if cache_key is not None:
                _cache_set(cache_key, rendered, cache_size)
            return rendered
        except Exception:
            pass  # fall through to mathtext

    rendered = _render_mathtext(latex, config, tag=tag)
    if cache_key is not None:
        _cache_set(cache_key, rendered, cache_size)
    return rendered


# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------


def _draw_tag(canvas: Image.Image, tag: int, config: LatexConfig) -> None:
    """Draw an equation number at the right edge of the canvas.

    Args:
        canvas: Canvas receiving the rendered formula and tag.
        tag: Equation number to draw.
        config: Active LaTeX rendering configuration.

    Returns:
        ``None``. The tag is drawn onto the provided canvas.
    """
    draw = ImageDraw.Draw(canvas)
    text = f"({tag})"

    # Font: Computer Modern Roman from matplotlib's bundled fonts — matches LaTeX
    font_size_px = round(config.font_size / 72.27 * config.dpi)
    font = _tag_font(font_size_px)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    x = canvas.width - text_w - _edge_padding(config)
    y = (canvas.height - text_h) // 2 - bbox[1]

    r, g, b = (round(c * 255) for c in _matplotlib_colors().to_rgb(config.color))
    draw.text((x, y), text, font=font, fill=(r, g, b))


@lru_cache(maxsize=16)
def _tag_font(font_size_px: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Load and cache the font used for equation numbering tags.

    Args:
        font_size_px: Requested font size in pixels.

    Returns:
        A Pillow font object suitable for equation tags.
    """
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont
    matplotlib_mod = _matplotlib_module()
    font_dir = _Path(matplotlib_mod.__file__).parent / "mpl-data" / "fonts" / "ttf"
    try:
        font = ImageFont.truetype(str(font_dir / "cmr10.ttf"), font_size_px)
    except (IOError, OSError):
        try:
            font = ImageFont.truetype(str(font_dir / "DejaVuSans.ttf"), font_size_px)
        except (IOError, OSError):
            font = ImageFont.load_default()
    return font


def _trim_and_pad(png_bytes: bytes, config: LatexConfig, tag: int | None = None) -> bytes:
    """Trim, fit, and center a rendered formula on the target canvas.

    Args:
        png_bytes: Raw rendered PNG bytes for the formula.
        config: Active LaTeX rendering configuration.
        tag: Optional equation number rendered beside the formula.

    Returns:
        PNG bytes for the trimmed and padded formula image.
    """
    img = _trim_to_content(Image.open(io.BytesIO(png_bytes)).convert("RGB"), config.background)
    max_formula_width = _available_formula_width(config, tag)
    if img.width > max_formula_width:
        scale = max_formula_width / img.width
        resized_height = max(1, round(img.height * scale))
        img = img.resize((max_formula_width, resized_height), _lanczos_resample())

    pad_px = max(0, int(config.padding))
    formula_left = _edge_padding(config)
    formula_width = _available_formula_width(config, tag)
    x = formula_left + max((formula_width - img.width) // 2, 0)
    canvas = Image.new(
        "RGB",
        (config.image_width, img.height + 2 * pad_px),
        config.background,
    )
    canvas.paste(img, (x, pad_px))
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
    """Render a formula with matplotlib's built-in mathtext engine.

    Args:
        latex: Display-math LaTeX source to render.
        config: Active LaTeX rendering configuration.
        tag: Optional equation number rendered beside the formula.

    Returns:
        A ``data:image/png`` URI containing the rendered formula.
    """
    fitted_config, png_bytes = _fit_latex_render(
        config,
        tag,
        lambda current_config: _render_mathtext_png(latex, current_config),
    )
    data = base64.b64encode(_trim_and_pad(png_bytes, fitted_config, tag=tag)).decode("ascii")
    return f"data:image/png;base64,{data}"


def _render_mathtext_png(latex: str, config: LatexConfig) -> bytes:
    """Render a mathtext expression to tightly bounded PNG bytes.

    Args:
        latex: Display-math LaTeX source to render.
        config: Active LaTeX rendering configuration.

    Returns:
        Raw PNG bytes for the rendered formula.
    """
    plt = _matplotlib_pyplot()

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
        return buf.read()
    finally:
        plt.close(fig)


def _color_to_html(color: str) -> str:
    """Convert a matplotlib color spec to an uppercase HTML hex string.

    Args:
        color: Matplotlib color specification to convert.

    Returns:
        A six-digit uppercase hex string without the leading ``#``.
    """
    r, g, b = _matplotlib_colors().to_rgb(color)
    return f"{round(r * 255):02X}{round(g * 255):02X}{round(b * 255):02X}"


def _color_to_dvipng(color: str) -> str:
    """Convert a matplotlib color spec to dvipng ``rgb R G B`` syntax.

    Args:
        color: Matplotlib color specification to convert.

    Returns:
        A dvipng-compatible color string.
    """
    r, g, b = _matplotlib_colors().to_rgb(color)
    return f"rgb {r:.6f} {g:.6f} {b:.6f}"


def _validate_usetex_inputs(latex: str, preamble: str) -> None:
    """Validate TeX inputs before invoking external LaTeX tooling.

    Args:
        latex: Display-math LaTeX source to validate.
        preamble: Extra LaTeX preamble text to validate.

    Returns:
        ``None``. Raises when the LaTeX input violates safety checks.
    """
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
    """Render a formula through the external LaTeX and dvipng pipeline.

    Args:
        latex: Display-math source to render.
        config: Active LaTeX rendering configuration.
        preamble: Extra LaTeX preamble text to prepend.
        tag: Optional equation number rendered beside the formula.

    Returns:
        A ``data:image/png`` URI containing the rendered formula.
    """
    fitted_config, png_bytes = _fit_latex_render(
        config,
        tag,
        lambda current_config: _render_usetex_png(latex, current_config, preamble),
    )
    data = base64.b64encode(_trim_and_pad(png_bytes, fitted_config, tag=tag)).decode("ascii")
    return f"data:image/png;base64,{data}"


def _render_usetex_png(latex: str, config: LatexConfig, preamble: str = "") -> bytes:
    """
    Direct latex + dvipng pipeline.

    Unlike matplotlib's usetex mode (which remaps all DVI colors to the text
    color before compositing), dvipng --truecolor renders DVI color specials
    faithfully, so \\color{} commands in formulas produce correctly colored output.

    Args:
        latex: Display-math LaTeX source to render.
        config: Active LaTeX rendering configuration.
        preamble: Extra LaTeX preamble text to prepend.

    Returns:
        Raw PNG bytes for the rendered formula.
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

        return png_path.read_bytes()


def _fit_latex_render(
    config: LatexConfig,
    tag: int | None,
    render_png,
) -> tuple[LatexConfig, bytes]:
    """Retry wide equations with smaller fonts before final composition.

    Args:
        config: Starting LaTeX rendering configuration.
        tag: Optional equation number rendered beside the formula.
        render_png: Callable that renders PNG bytes for a config variant.

    Returns:
        A tuple of the fitted config and its rendered PNG bytes.
    """
    current_config = config
    png_bytes = render_png(current_config)
    min_font_size = min(current_config.font_size, max(_MIN_AUTO_FONT_SIZE, round(config.font_size * 0.6)))

    for _ in range(4):
        content_width = _trimmed_content_width(png_bytes, current_config.background)
        if content_width <= _available_formula_width(current_config, tag):
            return current_config, png_bytes
        if current_config.font_size <= min_font_size:
            break

        target_font_size = max(
            min_font_size,
            int(current_config.font_size * _available_formula_width(current_config, tag) / max(content_width, 1)),
        )
        if target_font_size >= current_config.font_size:
            target_font_size = current_config.font_size - 1
        if target_font_size < min_font_size:
            target_font_size = min_font_size
        if target_font_size == current_config.font_size:
            break

        current_config = replace(current_config, font_size=target_font_size)
        png_bytes = render_png(current_config)

    return current_config, png_bytes


def _trimmed_content_width(png_bytes: bytes, background: str) -> int:
    """Measure the width of non-background pixels in a rendered PNG.

    Args:
        png_bytes: Rendered PNG image bytes.
        background: Background color used for trimming comparisons.

    Returns:
        The width in pixels of the trimmed content region.
    """
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return _trim_to_content(img, background).width


def _trim_to_content(img: Image.Image, background: str) -> Image.Image:
    """Crop away uniform background margins from an image.

    Args:
        img: PIL image to trim.
        background: Background color that should be removed.

    Returns:
        A cropped image when content exists, otherwise the original image.
    """
    bg = Image.new("RGB", img.size, background)
    bbox = ImageChops.difference(img, bg).getbbox()
    if bbox:
        return img.crop(bbox)
    return img


def _edge_padding(config: LatexConfig) -> int:
    """Compute horizontal gutter space for centered formula rendering.

    Args:
        config: Active LaTeX rendering configuration.

    Returns:
        Horizontal padding in pixels reserved at each edge.
    """
    base = max(int(config.padding) // 3, _MIN_EDGE_PADDING)
    return max(4, min(base, _MAX_EDGE_PADDING, max(config.image_width // 8, 4)))


def _available_formula_width(config: LatexConfig, tag: int | None) -> int:
    """Compute the horizontal space available for the formula body.

    Args:
        config: Active LaTeX rendering configuration.
        tag: Optional equation number rendered beside the formula.

    Returns:
        The maximum formula width in pixels after padding and tag space.
    """
    edge_pad = _edge_padding(config)
    reserved_tag_width = 0
    if tag is not None:
        reserved_tag_width = _tag_size(tag, config)[0] + edge_pad
    return max(1, config.image_width - 2 * edge_pad - reserved_tag_width)


def _tag_size(tag: int, config: LatexConfig) -> tuple[int, int]:
    """Measure the pixel size of a rendered equation-number tag.

    Args:
        tag: Equation number to render.
        config: Active LaTeX rendering configuration.

    Returns:
        A ``(width, height)`` tuple for the rendered tag text.
    """
    text = f"({tag})"
    font_size_px = round(config.font_size / 72.27 * config.dpi)
    font = _tag_font(font_size_px)
    probe = Image.new("RGB", (1, 1), config.background)
    bbox = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _lanczos_resample() -> int:
    """Return the best available Pillow constant for Lanczos resampling.

    Args:
        None.

    Returns:
        The Pillow resampling enum or legacy constant for Lanczos.
    """
    resampling = getattr(Image, "Resampling", None)
    if resampling is not None:
        return resampling.LANCZOS
    return Image.LANCZOS
