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
from .html_builder import build_page
from .renderers.code_renderer import render_code, render_output_text
from .renderers.inline_latex import convert_inline_math
from .renderers.latex_renderer import extract_display_math, render_latex_block

# Strip ANSI colour codes from tracebacks
_ANSI = re.compile(r"\x1b\[[0-9;]*[mGKFHJ]")

# Markdown extensions used for cell conversion
_MD_EXTENSIONS = ["extra", "sane_lists", "nl2br"]


class Converter:
    def __init__(self, config: Config) -> None:
        self.config = config

    def convert(self, notebook_path: Path) -> str:
        nb = nbformat.read(str(notebook_path), as_version=4)
        self._lang = _notebook_language(nb)

        parts: list[str] = []
        for cell in nb.cells:
            if cell.cell_type == "markdown":
                parts.append(self._markdown_cell(cell))
            elif cell.cell_type == "code":
                html = self._code_cell(cell)
                if html:
                    parts.append(html)
            # raw cells are skipped

        return build_page("\n".join(parts))

    # ------------------------------------------------------------------
    # Cell processors
    # ------------------------------------------------------------------

    def _markdown_cell(self, cell) -> str:
        src = cell.source

        # 1. Replace display-math blocks with inline Markdown images
        blocks = extract_display_math(src)
        chunks: list[str] = []
        prev = 0
        for start, end, latex in blocks:
            chunks.append(src[prev:start])
            try:
                uri = render_latex_block(latex, self.config.latex)
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

        # 3. Markdown → HTML
        html = markdown.markdown(src, extensions=_MD_EXTENSIONS)
        return f'<div class="md-cell">{html}</div>\n'

    def _code_cell(self, cell) -> str:
        parts: list[str] = []

        if cell.source.strip():
            png = render_code(cell.source, self._lang, self.config.code)
            uri = _png_uri(png)
            parts.append(f'<img class="code-img" src="{uri}" alt="code">\n')

        for output in cell.get("outputs", []):
            fragment = self._render_output(output)
            if fragment:
                parts.append(fragment)

        if not parts:
            return ""
        return '<div class="code-cell">\n' + "".join(parts) + "</div>\n"

    def _render_output(self, output) -> str:
        otype = output.get("output_type", "")

        # ---- stream (stdout / stderr) ----
        if otype == "stream":
            text = "".join(output.get("text", []))
            if not text.strip():
                return ""
            png = render_output_text(text, self.config.code)
            return f'<img class="output-img" src="{_png_uri(png)}" alt="output">\n'

        # ---- rich display / execute_result ----
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

            if "text/plain" in data:
                text = data["text/plain"]
                if isinstance(text, list):
                    text = "".join(text)
                if text.strip():
                    png = render_output_text(text, self.config.code)
                    return f'<img class="output-img" src="{_png_uri(png)}" alt="output">\n'

        # ---- error / traceback ----
        if otype == "error":
            tb = "\n".join(output.get("traceback", []))
            tb = _ANSI.sub("", tb)
            if tb.strip():
                png = render_output_text(tb, self.config.code)
                return f'<img class="output-img error-img" src="{_png_uri(png)}" alt="error">\n'

        return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _png_uri(png_bytes: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


def _notebook_language(nb) -> str:
    try:
        meta = nb.metadata
        lang = meta.get("kernelspec", {}).get("language", "")
        if not lang:
            lang = meta.get("language_info", {}).get("name", "")
        return lang or "python"
    except Exception:
        return "python"
