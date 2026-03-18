"""
Main conversion orchestrator for in-memory notebook models.

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
import logging
import re
import warnings
from pathlib import Path
from typing import Any

import html as html_mod

import markdown
import nbformat
from markdown.extensions import Extension
from markdown.inlinepatterns import SimpleTagInlineProcessor

from .config import Config
from .config import SafetyConfig
# Platform-specific HTML wrapping is now done in CLI
from .renderers.code_renderer import render_code, render_output_text, vstack_and_pad
from .renderers.inline_latex import convert_inline_math
from .renderers.latex_renderer import extract_display_math, render_latex_block
from .renderers.table_renderer import render_tables_as_images
from .sanitizer import sanitize_fragment

# Strip ANSI colour codes from tracebacks
_ANSI = re.compile(r"\x1b\[[0-9;]*[mGKFHJ]")

# Equation label / cross-reference patterns
# (?<!\\) prevents matching when the backslash is itself escaped (\\label / \\eqref),
# allowing users to write \\eqref{...} to display the literal command name.
_LABEL_RE = re.compile(r"(?<!\\)\\label\{([^}]+)\}")
_EQREF_RE = re.compile(r"(?<!\\)\\eqref\{([^}]+)\}")

# Fenced code blocks — protected from all LaTeX processing.
# Matches backtick or tilde fences (3+ identical fence chars) with optional language tag.
_FENCED_CODE_RE = re.compile(
    r"^((?:`{3,}|~{3,}))[^\n]*\n.*?\1[ \t]*$",
    re.MULTILINE | re.DOTALL,
)
_INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")
_PROTECTED_TOKEN = "\x00PROTECTED{}\x00"
_LIST_ITEM_RE = re.compile(
    r"^[ \t]{0,3}(?:[*+-][ \t]+\S.*|\d+[.)][ \t]+\S.*)$"
)
_NON_PARAGRAPH_LINE_RE = re.compile(
    r"^[ \t]{0,3}(?:[*+-][ \t]+\S|\d+[.)][ \t]+\S|>|#|`{3,}|~{3,}|\|)"
)

_STRIKETHROUGH_PATTERN = r"(?<!~)(~~)(.+?)(~~)(?!~)"
_MD_BASE_EXTENSIONS = ("extra", "sane_lists", "nl2br")
logger = logging.getLogger(__name__)


class _StrikethroughExtension(Extension):
    """Enable GitHub-style ~~strikethrough~~ spans in Python-Markdown."""

    def extendMarkdown(self, md) -> None:
        """Register the custom inline processor with Markdown.

        Args:
            md: Active Python-Markdown instance being configured.

        Returns:
            ``None``. The processor is registered in the parser.
        """
        md.inlinePatterns.register(
            SimpleTagInlineProcessor(_STRIKETHROUGH_PATTERN, "del"),
            "strikethrough",
            175,
        )


def _markdown_extensions() -> list[str | Extension]:
    """Return the Markdown extensions used for notebook cell conversion.

    Args:
        None.

    Returns:
        A list of extension names and extension instances.
    """
    return [*_MD_BASE_EXTENSIONS, _StrikethroughExtension()]

_RICH_OUTPUT_MIMES = frozenset({"image/png", "image/svg+xml", "text/html"})


class Converter:
    """Converts an in-memory Jupyter notebook model into HTML content fragments."""

    def __init__(
        self,
        config: Config,
        *,
        execute: bool = False,
        warnings_mode: bool = False,
    ) -> None:
        """Store conversion settings for notebook-to-HTML rendering.

        Args:
            config: Resolved nb2wb configuration object.
            execute: Whether code cells should be executed before rendering.
            warnings_mode: Whether ``stderr`` stream output should be shown.

        Returns:
            ``None``. The converter stores the provided settings.
        """
        self.config = config
        self.execute = execute
        self.warnings_mode = warnings_mode

    def convert_notebook(self, notebook, *, cwd: Path | None = None) -> str:
        """Convert an in-memory notebook object into HTML fragments.

        Args:
            notebook: Notebook model to convert.
            cwd: Optional working directory used when executing code cells.

        Returns:
            Combined HTML for all rendered notebook cells.
        """
        logger.debug(
            "Converter starting (execute=%s, warnings_mode=%s, cwd=%s)",
            self.execute,
            self.warnings_mode,
            cwd or Path.cwd(),
        )
        _enforce_serialized_notebook_size(notebook, self.config.safety)
        nb = _execute_cells(notebook, cwd or Path.cwd()) if self.execute else notebook
        _enforce_notebook_limits(nb, self.config.safety)
        self._markdown_parser = markdown.Markdown(extensions=_markdown_extensions())
        self._lang = _notebook_language(nb)
        self._latex_preamble = _collect_latex_preamble(nb.cells)
        self._eq_labels = _collect_equation_labels(nb.cells)
        self._table_mode_image = str(self.config.table.mode).lower() == "image"

        parts: list[str] = []
        skipped_cells = 0
        for index, cell in enumerate(nb.cells, start=1):
            tags = _cell_tags(cell)
            if _skip_cell(tags):
                skipped_cells += 1
                logger.debug(
                    "Skipping cell %d (type=%s, tags=%s)",
                    index,
                    cell.cell_type,
                    sorted(tags),
                )
                continue
            logger.debug("Rendering cell %d (type=%s)", index, cell.cell_type)
            if cell.cell_type == "markdown":
                parts.append(self._markdown_cell(cell))
            elif cell.cell_type == "code":
                html = self._code_cell(cell, tags)
                if html:
                    parts.append(html)
            # raw cells are skipped

        rendered = "\n".join(parts)
        logger.debug(
            "Converter finished (cells=%d, skipped=%d, fragments=%d, output_chars=%d)",
            len(nb.cells),
            skipped_cells,
            len(parts),
            len(rendered),
        )
        return rendered

    # ------------------------------------------------------------------
    # Cell processors
    # ------------------------------------------------------------------

    def _markdown_cell(self, cell) -> str:
        """Render a markdown cell to HTML with math-aware preprocessing.

        Args:
            cell: Notebook markdown cell to render.

        Returns:
            HTML fragment for the rendered markdown cell.
        """
        src, stash = _protect_markdown_code_spans(cell.source)

        # 0. Substitute \eqref{label} → (N) throughout
        def _eqref_sub(m: re.Match) -> str:
            """Replace a LaTeX equation reference with its numeric label.

            Args:
                m: Regex match for an ``\\eqref{...}`` occurrence.

            Returns:
                The rendered equation number or the original match text.
            """
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
                uri = render_latex_block(
                    latex,
                    self.config.latex,
                    self._latex_preamble,
                    tag=tag_num,
                )
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
        src = _normalize_cuddled_lists(src)

        # Restore fenced code blocks and inline code spans before markdown parsing
        src = _restore_protected_spans(src, stash)

        # 3. Markdown → HTML
        parser = getattr(self, "_markdown_parser", None)
        if parser is None:
            parser = markdown.Markdown(extensions=_markdown_extensions())
            self._markdown_parser = parser
        html = parser.reset().convert(src)
        if getattr(self, "_table_mode_image", str(self.config.table.mode).lower() == "image"):
            html = render_tables_as_images(html, self.config.table)
        html = _sanitize_html_fragment(html, profile="html")
        return f'<div class="md-cell">{html}</div>\n'

    def _code_cell(self, cell, tags: frozenset[str] = frozenset()) -> str:
        """Render a code cell and its outputs to an HTML fragment.

        Args:
            cell: Notebook code cell to render.
            tags: Cell tags controlling visibility and rendering behavior.

        Returns:
            HTML fragment for the rendered code cell, or an empty string.
        """
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
        """Render text-based outputs to PNG for later stacking.

        Args:
            output: Notebook output object to inspect and render.

        Returns:
            PNG bytes for text-like outputs, or ``None`` for rich outputs.
        """
        otype = output.get("output_type", "")

        if otype == "stream":
            if output.get("name") == "stderr" and not self.warnings_mode:
                return None
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
        """Render non-empty text output as PNG bytes.

        Args:
            text: Output text to render.

        Returns:
            PNG bytes for the text, or ``None`` when the text is empty.
        """
        if text.strip():
            return render_output_text(text, self.config.code, apply_padding=False)

        return None

    def _render_output(self, output) -> str:
        """Render rich notebook outputs as embeddable HTML fragments.

        Args:
            output: Notebook output object to inspect and render.

        Returns:
            HTML fragment for the rich output, or an empty string.
        """
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
            sanitized = _sanitize_html_fragment(raw_html, profile="html")
            return f'<div class="html-output">{sanitized}</div>\n'

        return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _png_uri(png_bytes: bytes) -> str:
    """Encode raw PNG bytes as a data URI.

    Args:
        png_bytes: PNG image bytes to encode.

    Returns:
        A ``data:image/png`` URI containing the image bytes.
    """
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


def _svg_data_uri(svg: str) -> str:
    """Encode sanitized SVG markup as a data URI.

    Args:
        svg: Raw SVG markup to sanitize and encode.

    Returns:
        A ``data:image/svg+xml`` URI containing the sanitized SVG.
    """
    sanitized = _sanitize_html_fragment(svg, profile="svg")
    encoded = base64.b64encode(sanitized.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _sanitize_html_fragment(fragment: str, *, profile: str = "html") -> str:
    """Sanitize notebook-provided HTML or SVG fragments.

    Args:
        fragment: Raw HTML or SVG fragment to sanitize.
        profile: Sanitizer profile name, either ``html`` or ``svg``.

    Returns:
        Sanitized fragment text, or an empty string on sanitizer failure.
    """
    try:
        return sanitize_fragment(fragment, profile=profile)
    except Exception:
        return ""


def _apply_eq_tag(latex: str, eq_labels: dict[str, int]) -> tuple[str, int | None]:
    """Remove LaTeX labels while resolving an optional equation tag number.

    Args:
        latex: Display-math LaTeX source to normalize.
        eq_labels: Mapping of equation labels to assigned numbers.

    Returns:
        A tuple of cleaned LaTeX text and an optional tag number.
    """
    tag_num = None

    def _sub(m: re.Match) -> str:
        """Remove a LaTeX label command while capturing its tag number.

        Args:
            m: Regex match for a ``\\label{...}`` command.

        Returns:
            An empty string so the label command is removed from the formula.
        """
        nonlocal tag_num
        n = eq_labels.get(m.group(1))
        if n is not None:
            tag_num = n
        return ""

    clean = _LABEL_RE.sub(_sub, latex).strip()
    return clean, tag_num


def _join_text(value: Any, *, sep: str = "") -> str:
    """Normalize notebook text payloads that may be strings or string lists.

    Args:
        value: Notebook payload value to normalize.
        sep: Separator inserted between list items when joining.

    Returns:
        A normalized text string.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return sep.join(part for part in value if isinstance(part, str))
    return ""


def _rich_output_data(output: dict[str, Any]) -> dict[str, Any] | None:
    """Return the rich-output data payload for display outputs.

    Args:
        output: Notebook output mapping to inspect.

    Returns:
        The ``data`` mapping for rich outputs, or ``None`` otherwise.
    """
    if output.get("output_type", "") not in ("execute_result", "display_data"):
        return None
    data = output.get("data", {})
    return data if isinstance(data, dict) else {}


def _protect_markdown_code_spans(src: str) -> tuple[str, list[str]]:
    """Protect fenced and inline code spans from LaTeX transformations.

    Args:
        src: Markdown source that may contain code spans.

    Returns:
        A tuple of protected source text and stashed original spans.
    """
    stash: list[str] = []

    def _protect(match: re.Match) -> str:
        """Replace a code span with a protected placeholder token.

        Args:
            match: Regex match for a fenced or inline code span.

        Returns:
            Placeholder text that can be restored after LaTeX processing.
        """
        stash.append(match.group(0))
        return _PROTECTED_TOKEN.format(len(stash) - 1)

    src = _FENCED_CODE_RE.sub(_protect, src)
    src = _INLINE_CODE_RE.sub(_protect, src)
    return src, stash


def _restore_protected_spans(src: str, stash: list[str]) -> str:
    """Restore code spans previously replaced with placeholder tokens.

    Args:
        src: Protected source text containing placeholder tokens.
        stash: Original code spans indexed by placeholder position.

    Returns:
        Source text with original code spans restored.
    """
    for i, block in enumerate(stash):
        src = src.replace(_PROTECTED_TOKEN.format(i), block)
    return src


def _normalize_cuddled_lists(src: str) -> str:
    """Insert blank lines before top-level lists cuddled against prose.

    Args:
        src: Markdown source to normalize.

    Returns:
        Markdown source with list spacing normalized.
    """
    if not src:
        return src

    lines = src.splitlines()
    if not lines:
        return src

    out: list[str] = []
    for line in lines:
        if _LIST_ITEM_RE.match(line):
            prev = out[-1] if out else ""
            if prev.strip() and not _NON_PARAGRAPH_LINE_RE.match(prev):
                out.append("")
        out.append(line)

    normalized = "\n".join(out)
    if src.endswith("\n"):
        normalized += "\n"
    return normalized


def _cell_tags(cell) -> frozenset[str]:
    """Return the normalized set of tags attached to a notebook cell.

    Args:
        cell: Notebook cell whose metadata should be inspected.

    Returns:
        A frozenset of tag strings.
    """
    try:
        return frozenset(cell.metadata.get("tags", []))
    except (AttributeError, TypeError):
        return frozenset()


def _skip_cell(tags: frozenset[str]) -> bool:
    """Check whether a cell should be omitted from rendered output.

    Args:
        tags: Cell tag set to inspect.

    Returns:
        ``True`` when the cell should be skipped.
    """
    return "hide-cell" in tags or "latex-preamble" in tags


def _collect_latex_preamble(cells) -> str:
    """Collect LaTeX preamble snippets from tagged markdown cells.

    Args:
        cells: Notebook cells to scan for preamble fragments.

    Returns:
        Combined LaTeX preamble text.
    """
    preamble_parts: list[str] = []
    for cell in cells:
        if "latex-preamble" in _cell_tags(cell):
            source = _join_text(getattr(cell, "source", ""))
            if source.strip():
                preamble_parts.append(source.strip())
    return "\n".join(preamble_parts)


def _collect_equation_labels(cells) -> dict[str, int]:
    """Collect document-level equation labels in source order.

    Args:
        cells: Notebook cells to scan for labeled display equations.

    Returns:
        Mapping of equation labels to assigned display numbers.
    """
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


def _enforce_serialized_notebook_size(nb, safety: SafetyConfig) -> None:
    """Reject oversized notebooks using serialized JSON byte size.

    Args:
        nb: Notebook payload to size-check.
        safety: Safety limits controlling maximum accepted input size.

    Returns:
        ``None``. Raises when the payload exceeds the configured limit.
    """
    try:
        serialized = nbformat.writes(nb)
    except Exception as exc:
        raise ValueError(f"Unable to serialize notebook payload: {exc}") from exc
    size = len(serialized.encode("utf-8", errors="ignore"))
    if size > safety.max_input_bytes:
        raise ValueError(
            f"Notebook payload exceeds safety limit ({size} bytes > {safety.max_input_bytes})."
        )


def _enforce_notebook_limits(nb, safety: SafetyConfig) -> None:
    """Apply notebook safety limits for size, cells, math, and outputs.

    Args:
        nb: Notebook payload to validate.
        safety: Safety limits controlling notebook resource usage.

    Returns:
        ``None``. Raises when a configured limit is exceeded.
    """
    cells = getattr(nb, "cells", [])
    if len(cells) > safety.max_cells:
        raise ValueError(
            f"Notebook has too many cells ({len(cells)} > {safety.max_cells})."
        )

    total_output_bytes = 0
    total_display_math_blocks = 0
    total_latex_chars = 0
    for idx, cell in enumerate(cells):
        source = _join_text(getattr(cell, "source", ""))
        if len(source) > safety.max_cell_source_chars:
            raise ValueError(
                f"Cell {idx} source too large "
                f"({len(source)} > {safety.max_cell_source_chars} chars)."
            )

        if getattr(cell, "cell_type", "") == "markdown":
            blocks = extract_display_math(source)
            total_display_math_blocks += len(blocks)
            total_latex_chars += sum(len(latex) for _, _, latex in blocks)
            if total_display_math_blocks > safety.max_display_math_blocks:
                raise ValueError(
                    "Notebook has too many display-math blocks "
                    f"({total_display_math_blocks} > {safety.max_display_math_blocks})."
                )
            if total_latex_chars > safety.max_total_latex_chars:
                raise ValueError(
                    "Notebook has too much display-math content "
                    f"({total_latex_chars} > {safety.max_total_latex_chars} chars)."
                )

        for output in cell.get("outputs", []):
            total_output_bytes += _estimate_payload_size(output)
            if total_output_bytes > safety.max_total_output_bytes:
                raise ValueError(
                    "Notebook outputs exceed safety limit "
                    f"({total_output_bytes} > {safety.max_total_output_bytes} bytes)."
                )


def _estimate_payload_size(value: Any) -> int:
    """Estimate the byte footprint of a nested notebook output payload.

    Args:
        value: Arbitrary payload value to size recursively.

    Returns:
        Estimated payload size in bytes.
    """
    if value is None:
        return 0
    if isinstance(value, bytes):
        return len(value)
    if isinstance(value, str):
        return len(value.encode("utf-8", errors="ignore"))
    if isinstance(value, (int, float, bool)):
        return 8
    if isinstance(value, list):
        return sum(_estimate_payload_size(v) for v in value)
    if isinstance(value, dict):
        return sum(_estimate_payload_size(k) + _estimate_payload_size(v) for k, v in value.items())
    return 0


def _notebook_language(nb) -> str:
    """Detect the notebook language from metadata with a Python fallback.

    Args:
        nb: Notebook payload whose metadata should be inspected.

    Returns:
        The detected notebook language name.
    """
    try:
        meta = nb.metadata
        lang = meta.get("kernelspec", {}).get("language", "")
        if not lang:
            lang = meta.get("language_info", {}).get("name", "")
        return lang or "python"
    except (AttributeError, TypeError):
        return "python"


def _execute_cells(nb, cwd: Path):
    """Execute notebook code cells through a Jupyter kernel.

    Args:
        nb: Notebook payload to execute in place.
        cwd: Working directory for notebook execution.

    Returns:
        The executed notebook payload.
    """
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
