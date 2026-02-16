"""
Parse Quarto Markdown (.qmd) files into an nbformat NotebookNode.

Quarto format summary
---------------------
- Optional YAML front matter between ``---`` delimiters.
- Fenced code chunks:  ```{lang [options]}  …  ```
- Cell options as ``#|`` comment lines at the top of a code chunk:
    #| echo: false        → hide-input tag
    #| output: false      → hide-output tag
    #| include: false     → hide-cell tag
    #| tags: [tag1, tag2] → arbitrary tags
- The special language ``{latex-preamble}`` marks a preamble block (the
  source is attached to a markdown cell with the ``latex-preamble`` tag).
- The special language ``{output}`` attaches pre-computed stdout to the
  immediately preceding code cell (no markdown may appear between them).
- Everything outside code chunks is treated as a markdown cell.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import nbformat
import yaml


# Matches a fenced code chunk: ```{lang...}\n…\n```
_CHUNK_RE = re.compile(
    r"^```\{(\w[\w.-]*)(.*?)\}[ \t]*\n(.*?)^```[ \t]*$",
    re.DOTALL | re.MULTILINE,
)

# YAML front matter at the very start of the file
_FRONT_MATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)


def read_qmd(path: Path) -> nbformat.NotebookNode:
    """
    Parse a ``.qmd`` file and return an ``nbformat`` notebook.

    Code cells contain only source by default, since ``.qmd`` files do not
    store execution results.  Pre-computed outputs can be embedded using
    ``{output}`` chunks immediately after the corresponding code chunk.
    Quarto cell options (``#|`` lines) are translated to Jupyter-compatible
    cell tags.
    """
    text = path.read_text(encoding="utf-8")
    front_matter, text = _split_front_matter(text)
    language = _detect_language(front_matter, text)

    cells = _extract_cells(text, language)

    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {"language": language, "name": language}
    nb.metadata["language_info"] = {"name": language}
    nb.cells = cells
    return nb


# ---------------------------------------------------------------------------
# Front matter
# ---------------------------------------------------------------------------

def _split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML front matter from the body, returning (parsed_dict, remaining_text)."""
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, text[m.end():]


def _detect_language(fm: dict[str, Any], text: str) -> str:
    """Detect the default language from front matter or the first code chunk."""
    # Explicit engine in front matter
    if "engine" in fm:
        return str(fm["engine"])
    # Jupyter kernel name
    jupyter = fm.get("jupyter", {})
    if isinstance(jupyter, dict) and "kernel" in jupyter:
        return str(jupyter["kernel"])
    # Infer from the first code chunk language
    _PSEUDO_LANGS = {"latex-preamble", "output"}
    for m in _CHUNK_RE.finditer(text):
        lang = m.group(1)
        if lang not in _PSEUDO_LANGS:
            return lang
    return "python"


# ---------------------------------------------------------------------------
# Cell extraction
# ---------------------------------------------------------------------------

def _extract_cells(text: str, default_lang: str) -> list[nbformat.NotebookNode]:
    """Parse the body of a .qmd file into a list of notebook cells."""
    cells: list[nbformat.NotebookNode] = []
    pos = 0
    last_code_cell: nbformat.NotebookNode | None = None

    for m in _CHUNK_RE.finditer(text):
        # Markdown before this chunk
        md = text[pos : m.start()].strip()
        if md:
            cells.append(nbformat.v4.new_markdown_cell(md))
            last_code_cell = None  # prose breaks output attachment

        lang = m.group(1)
        body = m.group(3)

        if lang == "output":
            # Attach pre-computed stdout to the immediately preceding code cell.
            # Use the raw chunk body so that lines starting with #| are preserved.
            if last_code_cell is not None and body.strip():
                text_out = body if body.endswith("\n") else body + "\n"
                last_code_cell["outputs"].append(
                    nbformat.from_dict({
                        "output_type": "stream",
                        "name": "stdout",
                        "text": text_out,
                    })
                )
            pos = m.end()
            continue

        tags, source = _parse_chunk(body)

        if lang == "latex-preamble":
            # Treat as a hidden markdown cell carrying the LaTeX preamble
            if "latex-preamble" not in tags:
                tags = ["latex-preamble"] + tags
            cell = nbformat.v4.new_markdown_cell(source)
            last_code_cell = None
        else:
            cell = nbformat.v4.new_code_cell(source)
            last_code_cell = cell

        if tags:
            cell.metadata["tags"] = tags

        cells.append(cell)
        pos = m.end()

    # Trailing markdown
    md = text[pos:].strip()
    if md:
        cells.append(nbformat.v4.new_markdown_cell(md))

    return cells


def _parse_chunk(body: str) -> tuple[list[str], str]:
    """
    Split a code-chunk body into (tags, source).

    ``#|`` option lines are stripped from the source and translated to tags.
    """
    tags: list[str] = []
    source_lines: list[str] = []
    in_options = True   # #| lines must appear before any real code

    for line in body.splitlines():
        stripped = line.lstrip()
        if in_options and stripped.startswith("#|"):
            opt = stripped[2:].strip()
            _apply_option(opt, tags)
        else:
            in_options = False
            source_lines.append(line)

    source = "\n".join(source_lines).strip()
    return tags, source


def _apply_option(opt: str, tags: list[str]) -> None:
    """Translate a single ``#|`` option string into zero or more cell tags."""
    key, _, value = opt.partition(":")
    key = key.strip()
    value = value.strip().lower()

    if key == "echo" and value == "false":
        tags.append("hide-input")
    elif key == "output" and value == "false":
        tags.append("hide-output")
    elif key in ("include", "eval") and value == "false":
        tags.append("hide-cell")
    elif key == "tags":
        # #| tags: [tag1, tag2]  or  #| tags: tag1
        raw = value.strip("[]")
        for t in raw.split(","):
            t = t.strip().strip("\"'")
            if t:
                tags.append(t)
