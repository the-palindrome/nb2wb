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

    Code cells contain only source (no outputs), since ``.qmd`` files do not
    store execution results.  Quarto cell options (``#|`` lines) are
    translated to Jupyter-compatible cell tags.
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
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, text[m.end():]


def _detect_language(fm: dict[str, Any], text: str) -> str:
    # Explicit engine in front matter
    if "engine" in fm:
        return str(fm["engine"])
    # Jupyter kernel name
    jupyter = fm.get("jupyter", {})
    if isinstance(jupyter, dict) and "kernel" in jupyter:
        return str(jupyter["kernel"])
    # Infer from the first code chunk language
    m = _CHUNK_RE.search(text)
    if m:
        lang = m.group(1)
        if lang not in ("latex-preamble",):
            return lang
    return "python"


# ---------------------------------------------------------------------------
# Cell extraction
# ---------------------------------------------------------------------------

def _extract_cells(text: str, default_lang: str) -> list[nbformat.NotebookNode]:
    cells: list[nbformat.NotebookNode] = []
    pos = 0

    for m in _CHUNK_RE.finditer(text):
        # Markdown before this chunk
        md = text[pos : m.start()].strip()
        if md:
            cells.append(nbformat.v4.new_markdown_cell(md))

        lang = m.group(1)
        body = m.group(3)
        tags, source = _parse_chunk(body)

        if lang == "latex-preamble":
            # Treat as a hidden markdown cell carrying the LaTeX preamble
            if "latex-preamble" not in tags:
                tags = ["latex-preamble"] + tags
            cell = nbformat.v4.new_markdown_cell(source)
        else:
            cell = nbformat.v4.new_code_cell(source)

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
