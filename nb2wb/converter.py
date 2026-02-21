"""
Main conversion orchestrator: reads a .ipynb and produces an HTML string.

Cell handling
-------------
Markdown cells
  1. Extract display-math blocks ($$…$$, \\[…\\], \\begin{equation}…),
     render each to a PNG image, substitute with a Markdown image reference.
  2. Convert remaining inline LaTeX ($…$) to Unicode.
  3. Convert the resulting Markdown to HTML.

Code cells
  1. Render the source as a syntax-highlighted image.
  2. Render each output:
       stream / error     → plain-text image
       image/png          → embed the notebook-stored image directly
       image/svg+xml      → embed the SVG inline
       text/html          → embed the HTML fragment
       text/plain         → plain-text image
"""
from __future__ import annotations

import base64
import re
import warnings
from pathlib import Path
from typing import Any

import html as html_mod

import markdown
import nbformat

from .config import Config
from .md_reader import read_md
from .qmd_reader import read_qmd
# Platform-specific HTML wrapping is now done in CLI
from .renderers.code_renderer import render_code, render_output_text, vstack_and_pad
from .renderers.inline_latex import convert_inline_math
from .renderers.latex_renderer import extract_display_math, render_latex_block

# Strip ANSI colour codes from tracebacks
_ANSI = re.compile(r"\x1b\[[0-9;]*[mGKFHJ]")

# Equation label / cross-reference patterns
# (?<!\\) prevents matching when the backslash is itself escaped (\\label / \\eqref),
# allowing users to write \\eqref{...} to display the literal command name.
_LABEL_RE = re.compile(r"(?<!\\)\\label\{([^}]+)\}")
_EQREF_RE = re.compile(r"(?<!\\)\\eqref\{([^}]+)\}")

# Fenced code blocks — protected from all LaTeX processing
# Matches ``` or ~~~  (3+ identical fence chars) with optional language tag
_FENCED_CODE_RE = re.compile(r"^(`{3,})[^\n]*\n.*?\1[ \t]*$", re.MULTILINE | re.DOTALL)
_INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")
_PROTECTED_TOKEN = "\x00PROTECTED{}\x00"

# Markdown extensions used for cell conversion
_MD_EXTENSIONS = ["extra", "sane_lists", "nl2br"]

_RICH_OUTPUT_MIMES = frozenset({"image/png", "image/svg+xml", "text/html"})

# Best-effort HTML sanitization for notebook-originated dynamic fragments.
_DANGEROUS_BLOCK_TAG_RE = re.compile(
    r"<\s*(script|iframe|object|embed)\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_DANGEROUS_SINGLE_TAG_RE = re.compile(
    r"<\s*(script|iframe|object|embed|link|meta)\b[^>]*?/?>",
    re.IGNORECASE,
)
_EVENT_ATTR_RE = re.compile(
    r"""\s+on[a-zA-Z0-9_-]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)""",
    re.IGNORECASE,
)
_JS_URI_QUOTED_RE = re.compile(
    r"""(\b(?:href|src|xlink:href)\s*=\s*)(["'])\s*javascript:[^"']*\2""",
    re.IGNORECASE,
)
_JS_URI_UNQUOTED_RE = re.compile(
    r"""(\b(?:href|src|xlink:href)\s*=\s*)javascript:[^\s>]+""",
    re.IGNORECASE,
)
_DATA_HTML_URI_QUOTED_RE = re.compile(
    r"""(\b(?:href|src|xlink:href)\s*=\s*)(["'])\s*data:text/html[^"']*\2""",
    re.IGNORECASE,
)
_DATA_HTML_URI_UNQUOTED_RE = re.compile(
    r"""(\b(?:href|src|xlink:href)\s*=\s*)data:text/html[^\s>]+""",
    re.IGNORECASE,
)


class Converter:
    """Converts a Jupyter notebook or Quarto document into HTML content fragments."""

    def __init__(self, config: Config, *, execute: bool = False) -> None:
        self.config = config
        self.execute = execute

    def convert(self, notebook_path: Path) -> str:
        """Convert a ``.ipynb``, ``.qmd``, or ``.md`` file to a concatenated HTML string.

        Reads the notebook, collects LaTeX preamble and equation labels across
        all cells, then renders each markdown and code cell to HTML fragments.
        """
        nb = _load_notebook(notebook_path, execute=self.execute)
        self._lang = _notebook_language(nb)
        self._latex_preamble = _collect_latex_preamble(nb.cells)
        self._eq_labels = _collect_equation_labels(nb.cells)

        parts: list[str] = []
        for cell in nb.cells:
            tags = _cell_tags(cell)
            if _skip_cell(tags):
                continue
            if cell.cell_type == "markdown":
                parts.append(self._markdown_cell(cell))
            elif cell.cell_type == "code":
                html = self._code_cell(cell, tags)
                if html:
                    parts.append(html)
            # raw cells are skipped

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Cell processors
    # ------------------------------------------------------------------

    def _markdown_cell(self, cell) -> str:
        """Render a markdown cell to HTML, processing LaTeX and equation references."""
        src, stash = _protect_markdown_code_spans(cell.source)

        # 0. Substitute \eqref{label} → (N) throughout
        def _eqref_sub(m: re.Match) -> str:
            n = self._eq_labels.get(m.group(1))
            return f"({n})" if n is not None else m.group(0)
        src = _EQREF_RE.sub(_eqref_sub, src)

        # 1. Replace display-math blocks with inline Markdown images
        blocks = extract_display_math(src)
        chunks: list[str] = []
        prev = 0
        for start, end, latex in blocks:
            chunks.append(src[prev:start])
            try:
                latex, tag_num = _apply_eq_tag(latex, self._eq_labels)
                uri = render_latex_block(latex, self.config.latex, self._latex_preamble, tag=tag_num)
                # Blank lines around the image so Markdown treats it as a block
                chunks.append(f"\n\n![math]({uri})\n\n")
            except Exception as exc:
                warnings.warn(
                    f"LaTeX render failed; leaving source block unchanged: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )
                chunks.append(src[start:end])
            prev = end
        chunks.append(src[prev:])
        src = "".join(chunks)

        # 2. Convert inline LaTeX to Unicode
        src = convert_inline_math(src)

        # Restore fenced code blocks and inline code spans before markdown parsing
        src = _restore_protected_spans(src, stash)

        # 3. Markdown → HTML
        html = markdown.markdown(src, extensions=_MD_EXTENSIONS)
        html = _sanitize_html_fragment(html)
        return f'<div class="md-cell">{html}</div>\n'

    def _code_cell(self, cell, tags: frozenset[str] = frozenset()) -> str:
        """Render a code cell (source + outputs) to an HTML ``<div>``."""
        # text-snippet: render as copyable HTML text instead of a PNG image
        if "text-snippet" in tags and cell.source.strip() and "hide-input" not in tags:
            escaped = html_mod.escape(cell.source)
            return (
                '<div class="code-cell">\n'
                f'<pre><code>{escaped}</code></pre>\n'
                '</div>\n'
            )

        png_parts: list[bytes] = []
        rich_parts: list[str] = []
        has_code = False
        footer_left = ""
        footer_right = ""

        if cell.source.strip() and "hide-input" not in tags:
            has_code = True
            cell_lang = cell.metadata.get("language", self._lang)
            ec = cell.get("execution_count")
            footer_left = f"[{ec}]" if ec is not None else "[ ]"
            footer_right = cell_lang.capitalize() if cell_lang else ""
            png_parts.append(
                render_code(cell.source, cell_lang, self.config.code,
                            apply_padding=False)
            )

        if "hide-output" not in tags:
            for output in cell.get("outputs", []):
                png = self._output_as_png(output)
                if png is not None:
                    png_parts.append(png)
                else:
                    fragment = self._render_output(output)
                    if fragment:
                        rich_parts.append(fragment)

        if not png_parts and not rich_parts:
            return ""

        parts: list[str] = []
        if png_parts:
            merged = vstack_and_pad(png_parts, self.config.code,
                                    draw_code_border=has_code,
                                    code_footer_left=footer_left,
                                    code_footer_right=footer_right)
            parts.append(f'<img class="code-img" src="{_png_uri(merged)}" alt="code">\n')
        parts.extend(rich_parts)

        return '<div class="code-cell">\n' + "".join(parts) + "</div>\n"

    def _output_as_png(self, output) -> bytes | None:
        """Render text-based outputs to PNG for merging; return None for rich outputs."""
        otype = output.get("output_type", "")

        if otype == "stream":
            return self._text_output_to_png(_join_text(output.get("text")))

        if otype == "error":
            traceback = _ANSI.sub("", _join_text(output.get("traceback"), sep="\n"))
            return self._text_output_to_png(traceback)

        data = _rich_output_data(output)
        if data is None:
            return None

        if any(mime in data for mime in _RICH_OUTPUT_MIMES):
            return None  # handled as a rich fragment

        return self._text_output_to_png(_join_text(data.get("text/plain")))

    def _text_output_to_png(self, text: str) -> bytes | None:
        """Render non-empty text output as PNG bytes."""
        if text.strip():
            return render_output_text(text, self.config.code, apply_padding=False)

        return None

    def _render_output(self, output) -> str:
        """Return HTML fragment for rich outputs (notebook PNG, SVG, HTML)."""
        data = _rich_output_data(output)
        if data is None:
            return ""

        raw_png = _join_text(data.get("image/png")).strip()
        if raw_png:
            return f'<img src="data:image/png;base64,{raw_png}" alt="output">\n'

        raw_svg = _join_text(data.get("image/svg+xml"))
        if raw_svg:
            return f'<img src="{_svg_data_uri(raw_svg)}" alt="output">\n'

        raw_html = _join_text(data.get("text/html"))
        if raw_html:
            sanitized = _sanitize_html_fragment(raw_html)
            return f'<div class="html-output">{sanitized}</div>\n'

        return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _png_uri(png_bytes: bytes) -> str:
    """Encode raw PNG bytes as a ``data:image/png;base64,...`` URI."""
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


def _svg_data_uri(svg: str) -> str:
    """Encode sanitized SVG markup as a data URI for safe embedding via <img>."""
    sanitized = _sanitize_html_fragment(svg)
    encoded = base64.b64encode(sanitized.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _sanitize_html_fragment(fragment: str) -> str:
    """Remove active-content vectors from notebook-provided HTML fragments."""
    cleaned = _DANGEROUS_BLOCK_TAG_RE.sub("", fragment)
    cleaned = _DANGEROUS_SINGLE_TAG_RE.sub("", cleaned)
    cleaned = _EVENT_ATTR_RE.sub("", cleaned)
    cleaned = _JS_URI_QUOTED_RE.sub(r"\1\2#\2", cleaned)
    cleaned = _JS_URI_UNQUOTED_RE.sub(r"\1#", cleaned)
    cleaned = _DATA_HTML_URI_QUOTED_RE.sub(r"\1\2#\2", cleaned)
    cleaned = _DATA_HTML_URI_UNQUOTED_RE.sub(r"\1#", cleaned)
    return cleaned


def _apply_eq_tag(latex: str, eq_labels: dict[str, int]) -> tuple[str, int | None]:
    """Strip \\label{...} from latex; return (clean_latex, tag_number_or_None)."""
    tag_num = None

    def _sub(m: re.Match) -> str:
        nonlocal tag_num
        n = eq_labels.get(m.group(1))
        if n is not None:
            tag_num = n
        return ""

    clean = _LABEL_RE.sub(_sub, latex).strip()
    return clean, tag_num


def _join_text(value: Any, *, sep: str = "") -> str:
    """Join rich-output text payloads that can be str or list[str]."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return sep.join(part for part in value if isinstance(part, str))
    return ""


def _rich_output_data(output: dict[str, Any]) -> dict[str, Any] | None:
    """Return ``output["data"]`` for rich outputs, otherwise ``None``."""
    if output.get("output_type", "") not in ("execute_result", "display_data"):
        return None
    data = output.get("data", {})
    return data if isinstance(data, dict) else {}


def _protect_markdown_code_spans(src: str) -> tuple[str, list[str]]:
    """Protect fenced and inline code spans from LaTeX transformations."""
    stash: list[str] = []

    def _protect(match: re.Match) -> str:
        stash.append(match.group(0))
        return _PROTECTED_TOKEN.format(len(stash) - 1)

    src = _FENCED_CODE_RE.sub(_protect, src)
    src = _INLINE_CODE_RE.sub(_protect, src)
    return src, stash


def _restore_protected_spans(src: str, stash: list[str]) -> str:
    """Restore code spans previously stashed by ``_protect_markdown_code_spans``."""
    for i, block in enumerate(stash):
        src = src.replace(_PROTECTED_TOKEN.format(i), block)
    return src


def _cell_tags(cell) -> frozenset[str]:
    """Return the set of tags on a cell (from cell.metadata.tags)."""
    try:
        return frozenset(cell.metadata.get("tags", []))
    except (AttributeError, TypeError):
        return frozenset()


def _skip_cell(tags: frozenset[str]) -> bool:
    """Return True when a cell should be excluded from final rendering."""
    return "hide-cell" in tags or "latex-preamble" in tags


def _collect_latex_preamble(cells) -> str:
    """Collect LaTeX preamble snippets from ``latex-preamble`` tagged cells."""
    preamble_parts: list[str] = []
    for cell in cells:
        if "latex-preamble" in _cell_tags(cell):
            source = _join_text(getattr(cell, "source", ""))
            if source.strip():
                preamble_parts.append(source.strip())
    return "\n".join(preamble_parts)


def _collect_equation_labels(cells) -> dict[str, int]:
    """Collect document-level equation labels in source order."""
    labels: dict[str, int] = {}
    counter = 1
    for cell in cells:
        tags = _cell_tags(cell)
        if _skip_cell(tags) or cell.cell_type != "markdown":
            continue
        source = _join_text(getattr(cell, "source", ""))
        for _, _, latex in extract_display_math(source):
            for match in _LABEL_RE.finditer(latex):
                label = match.group(1)
                if label in labels:
                    continue
                labels[label] = counter
                counter += 1
    return labels


def _load_notebook(notebook_path: Path, *, execute: bool) -> Any:
    """Load and optionally execute notebook-like sources."""
    suffix = notebook_path.suffix.lower()
    if suffix == ".qmd":
        nb = read_qmd(notebook_path)
    elif suffix == ".md":
        nb = read_md(notebook_path)
    else:
        nb = nbformat.read(str(notebook_path), as_version=4)

    return _execute_cells(nb, notebook_path.parent) if execute else nb


def _notebook_language(nb) -> str:
    """Detect the programming language of a notebook from its metadata, defaulting to Python."""
    try:
        meta = nb.metadata
        lang = meta.get("kernelspec", {}).get("language", "")
        if not lang:
            lang = meta.get("language_info", {}).get("name", "")
        return lang or "python"
    except (AttributeError, TypeError):
        return "python"


def _execute_cells(nb, cwd: Path):
    """Execute all code cells in *nb* via a Jupyter kernel and return the notebook."""
    try:
        from nbconvert.preprocessors import ExecutePreprocessor
    except ImportError:
        warnings.warn(
            "nbconvert not installed; skipping code-cell execution.",
            RuntimeWarning,
            stacklevel=2,
        )
        return nb

    lang = nb.metadata.get("kernelspec", {}).get("language", "python")
    # Map generic language names to installed kernel names
    kernel_name = "python3" if lang in ("python", "py") else lang

    ep = ExecutePreprocessor(timeout=300, kernel_name=kernel_name)
    try:
        ep.preprocess(nb, {"metadata": {"path": str(cwd)}})
    except Exception as exc:
        warnings.warn(
            f"Cell execution stopped early: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
    return nb
