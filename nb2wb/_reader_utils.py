"""
Shared helpers for Markdown/Quarto readers.
"""
from __future__ import annotations

import re
from typing import Any

import nbformat
import yaml

_FRONT_MATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML front matter from body, returning ``(front_matter, body)``."""
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        front_matter = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        front_matter = {}
    return front_matter, text[match.end():]


def make_notebook(
    cells: list[nbformat.NotebookNode],
    language: str,
) -> nbformat.NotebookNode:
    """Build a notebook with consistent language metadata."""
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {"language": language, "name": language}
    nb.metadata["language_info"] = {"name": language}
    nb.cells = cells
    return nb
