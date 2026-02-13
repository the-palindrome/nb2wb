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
from pathlib import Path

import markdown
import nbformat

from .config import Config
from .qmd_reader import read_qmd
from .html_builder import build_page
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

# Markdown extensions used for cell conversion
_MD_EXTENSIONS = ["extra", "sane_lists", "nl2br"]


class Converter:
    def __init__(self, config: Config) -> None:
        self.config = config

    def convert(self, notebook_path: Path) -> str:
        if notebook_path.suffix.lower() == ".qmd":
            nb = read_qmd(notebook_path)
            nb = _execute_cells(nb, notebook_path.parent)
        else:
            nb = nbformat.read(str(notebook_path), as_version=4)
        self._lang = _notebook_language(nb)

        # First pass: collect LaTeX preamble from tagged cells
        preamble_parts: list[str] = []
        for cell in nb.cells:
            if "latex-preamble" in _cell_tags(cell):
                src = cell.source if isinstance(cell.source, str) else "".join(cell.source)
                if src.strip():
                    preamble_parts.append(src.strip())
        self._latex_preamble = "\n".join(preamble_parts)

        # Second pass: collect equation labels for document-wide numbering
        self._eq_labels: dict[str, int] = {}
        _eq_counter = 1
        for cell in nb.cells:
            tags = _cell_tags(cell)
            if "hide-cell" in tags or "latex-preamble" in tags:
                continue
            if cell.cell_type == "markdown":
                for _, _, latex in extract_display_math(cell.source):
                    for lm in _LABEL_RE.finditer(latex):
                        label = lm.group(1)
                        if label not in self._eq_labels:
                            self._eq_labels[label] = _eq_counter
                            _eq_counter += 1

        parts: list[str] = []
        for cell in nb.cells:
            tags = _cell_tags(cell)
            if "hide-cell" in tags or "latex-preamble" in tags:
                continue
            if cell.cell_type == "markdown":
                parts.append(self._markdown_cell(cell))
            elif cell.cell_type == "code":
                html = self._code_cell(cell, tags)
                if html:
                    parts.append(html)
            # raw cells are skipped

        return build_page("\n".join(parts))

    # ------------------------------------------------------------------
    # Cell processors
    # ------------------------------------------------------------------

    def _markdown_cell(self, cell) -> str:
        src = cell.source

        # Protect fenced code blocks from all LaTeX processing by replacing
        # them with NUL-delimited placeholders, then restoring before parsing.
        _stash: list[str] = []

        def _protect(m: re.Match) -> str:
            _stash.append(m.group(0))
            return f"\x00CODEBLOCK{len(_stash) - 1}\x00"

        src = _FENCED_CODE_RE.sub(_protect, src)

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
                print(f"  [warn] LaTeX render failed: {exc}")
                chunks.append(src[start:end])
            prev = end
        chunks.append(src[prev:])
        src = "".join(chunks)

        # 2. Convert inline LaTeX to Unicode
        src = convert_inline_math(src)

        # Restore fenced code blocks before the markdown parser sees the source
        for i, block in enumerate(_stash):
            src = src.replace(f"\x00CODEBLOCK{i}\x00", block)

        # 3. Markdown → HTML
        html = markdown.markdown(src, extensions=_MD_EXTENSIONS)
        return f'<div class="md-cell">{html}</div>\n'

    def _code_cell(self, cell, tags: frozenset[str] = frozenset()) -> str:
        png_parts: list[bytes] = []
        rich_parts: list[str] = []

        if cell.source.strip() and "hide-input" not in tags:
            png_parts.append(
                render_code(cell.source, self._lang, self.config.code,
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
            merged = vstack_and_pad(png_parts, self.config.code)
            parts.append(f'<img class="code-img" src="{_png_uri(merged)}" alt="code">\n')
        parts.extend(rich_parts)

        return '<div class="code-cell">\n' + "".join(parts) + "</div>\n"

    def _output_as_png(self, output) -> bytes | None:
        """Render text-based outputs to PNG for merging; return None for rich outputs."""
        otype = output.get("output_type", "")

        if otype == "stream":
            text = "".join(output.get("text", []))
            if text.strip():
                return render_output_text(text, self.config.code, apply_padding=False)
            return None

        if otype in ("execute_result", "display_data"):
            data = output.get("data", {})
            if "image/png" in data or "image/svg+xml" in data or "text/html" in data:
                return None  # handled as a rich fragment
            if "text/plain" in data:
                text = data["text/plain"]
                if isinstance(text, list):
                    text = "".join(text)
                if text.strip():
                    return render_output_text(text, self.config.code, apply_padding=False)

        if otype == "error":
            tb = "\n".join(output.get("traceback", []))
            tb = _ANSI.sub("", tb)
            if tb.strip():
                return render_output_text(tb, self.config.code, apply_padding=False)

        return None

    def _render_output(self, output) -> str:
        """Return HTML fragment for rich outputs (notebook PNG, SVG, HTML)."""
        otype = output.get("output_type", "")

        if otype in ("execute_result", "display_data"):
            data = output.get("data", {})

            if "image/png" in data:
                raw = data["image/png"]
                if isinstance(raw, list):
                    raw = "".join(raw)
                return (
                    f'<img src="data:image/png;base64,{raw.strip()}"'
                    ' alt="output">\n'
                )

            if "image/svg+xml" in data:
                svg = data["image/svg+xml"]
                if isinstance(svg, list):
                    svg = "".join(svg)
                return f'<div class="svg-output">{svg}</div>\n'

            if "text/html" in data:
                html = data["text/html"]
                if isinstance(html, list):
                    html = "".join(html)
                return f'<div class="html-output">{html}</div>\n'

        return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _png_uri(png_bytes: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


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


def _cell_tags(cell) -> frozenset[str]:
    """Return the set of tags on a cell (from cell.metadata.tags)."""
    try:
        return frozenset(cell.metadata.get("tags", []))
    except Exception:
        return frozenset()


def _notebook_language(nb) -> str:
    try:
        meta = nb.metadata
        lang = meta.get("kernelspec", {}).get("language", "")
        if not lang:
            lang = meta.get("language_info", {}).get("name", "")
        return lang or "python"
    except Exception:
        return "python"


def _execute_cells(nb, cwd: Path):
    """Execute all code cells in *nb* via a Jupyter kernel and return the notebook."""
    try:
        from nbconvert.preprocessors import ExecutePreprocessor
    except ImportError:
        print("  [warn] nbconvert not installed; skipping cell execution for .qmd.")
        return nb

    lang = nb.metadata.get("kernelspec", {}).get("language", "python")
    # Map generic language names to installed kernel names
    kernel_name = "python3" if lang in ("python", "py") else lang

    ep = ExecutePreprocessor(timeout=300, kernel_name=kernel_name)
    try:
        ep.preprocess(nb, {"metadata": {"path": str(cwd)}})
    except Exception as exc:
        print(f"  [warn] Cell execution stopped early: {exc}")
    return nb
