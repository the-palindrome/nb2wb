"""
Parse plain Markdown (.md) files into an nbformat NotebookNode.

Markdown format support
-----------------------
- Optional YAML front matter between ``---`` delimiters.
- Standard fenced code blocks:  ```lang  ...  ```  (or ~~~)
- The special language ``latex-preamble`` marks a preamble block (the
  source is attached to a markdown cell with the ``latex-preamble`` tag).
- Inline tags on the fence line:  ```python hide-input  ...  ```
- HTML comment directives control cell visibility:
    <!-- nb2wb: hide-input -->       hides the code source
    <!-- nb2wb: hide-output -->      hides the output
    <!-- nb2wb: hide-cell -->        hides the entire cell
    <!-- nb2wb: tag1, tag2 -->       arbitrary tags
- Everything outside code blocks is treated as a markdown cell.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import nbformat
import yaml


# Standard fenced code block: ```lang [tags...]\n...\n```  (3+ backticks or tildes)
# Group 1: fence chars, Group 2: language, Group 3: rest of fence line (tags), Group 4: body
_MD_CODE_RE = re.compile(
    r"^(`{3,}|~{3,})(\S*)([ \t][^\n]*)?\n(.*?)^\1[ \t]*$",
    re.DOTALL | re.MULTILINE,
)

# nb2wb directives on their own line: <!-- nb2wb: hide-input -->
_NB2WB_COMMENT_RE = re.compile(
    r"^[ \t]*<!--\s*nb2wb\s*:\s*(.+?)\s*-->[ \t]*$",
    re.MULTILINE,
)

# YAML front matter at the very start of the file
_FRONT_MATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)


def read_md(path: Path) -> nbformat.NotebookNode:
    """
    Parse a ``.md`` file and return an ``nbformat`` notebook.

    Code cells contain only source by default.  Execution is opt-in via
    the ``--execute`` CLI flag (handled in the converter, not here).
    Each code block stores its language in ``cell.metadata["language"]``
    for per-cell syntax highlighting.
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
    """Detect the default language from front matter or the first code block."""
    if "language" in fm:
        return str(fm["language"])
    if "engine" in fm:
        return str(fm["engine"])
    jupyter = fm.get("jupyter", {})
    if isinstance(jupyter, dict) and "kernel" in jupyter:
        return str(jupyter["kernel"])
    # Infer from the first non-special code block
    _SPECIAL_LANGS = {"latex-preamble"}
    for m in _MD_CODE_RE.finditer(text):
        lang = m.group(2).strip()
        if lang and lang not in _SPECIAL_LANGS:
            # Strip fence-line tags from language (only want the lang itself)
            return lang
    return "python"


# ---------------------------------------------------------------------------
# Cell extraction
# ---------------------------------------------------------------------------

def _extract_cells(text: str, default_lang: str) -> list[nbformat.NotebookNode]:
    """Parse the body of a .md file into a list of notebook cells."""
    cells: list[nbformat.NotebookNode] = []
    pos = 0

    for m in _MD_CODE_RE.finditer(text):
        # Markdown between the previous code block and this one
        md_text = text[pos:m.start()]

        # Extract and consume nb2wb directives from the markdown
        pending_tags: list[str] = []
        md_text = _consume_directives(md_text, pending_tags)

        md_text = md_text.strip()
        if md_text:
            cells.append(nbformat.v4.new_markdown_cell(md_text))

        # Parse the code block
        lang = m.group(2).strip() or default_lang
        fence_rest = (m.group(3) or "").strip()
        body = m.group(4)

        # Parse space-separated tags from the fence line (e.g. ```python hide-input)
        fence_tags = fence_rest.split() if fence_rest else []
        all_tags = pending_tags + fence_tags

        if lang == "latex-preamble":
            # Hidden markdown cell carrying LaTeX preamble
            cell = nbformat.v4.new_markdown_cell(body.strip())
            all_tags = all_tags + ["latex-preamble"]
            cell.metadata["tags"] = all_tags
        else:
            cell = nbformat.v4.new_code_cell(body.strip())
            cell.metadata["language"] = lang
            if all_tags:
                cell.metadata["tags"] = all_tags

        cells.append(cell)
        pos = m.end()

    # Trailing markdown after the last code block
    md_text = text[pos:]
    pending_tags: list[str] = []
    md_text = _consume_directives(md_text, pending_tags)
    md_text = md_text.strip()
    if md_text:
        cells.append(nbformat.v4.new_markdown_cell(md_text))
    # Trailing directives not followed by a code block are discarded

    return cells


def _consume_directives(text: str, tags: list[str]) -> str:
    """Remove nb2wb HTML comment directives from *text*, collecting tags.

    Directives have the form ``<!-- nb2wb: tag1, tag2 -->``.
    Multiple directives are merged.  The cleaned text is returned.
    """
    def _collect(m: re.Match) -> str:
        directive = m.group(1)
        for part in directive.split(","):
            tag = part.strip()
            if tag:
                tags.append(tag)
        return ""

    return _NB2WB_COMMENT_RE.sub(_collect, text)
