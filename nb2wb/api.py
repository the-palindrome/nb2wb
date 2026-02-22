"""Programmatic API for server-side nb2wb usage."""
from __future__ import annotations

from copy import deepcopy
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

import nbformat

from .config import Config, apply_platform_defaults, load_config, load_config_from_dict
from .converter import Converter
from .md_reader import read_md_text
from .platforms import get_builder, list_platforms
from .qmd_reader import read_qmd_text

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_ALLOWED_INPUT_SUFFIXES = frozenset({".ipynb", ".qmd", ".md"})
_IPYNB_SUFFIXES = frozenset({".ipynb"})
_MD_SUFFIXES = frozenset({".md"})
_QMD_SUFFIXES = frozenset({".qmd"})
_TEXT_PAYLOAD_ALIASES: dict[str, str] = {
    "md": "md",
    "markdown": "md",
    "qmd": "qmd",
    "quarto": "qmd",
}
_QMD_CHUNK_RE = re.compile(r"^```\{(\w[\w.-]*)", re.MULTILINE)


def convert(
    notebook: str | Mapping[str, Any] | nbformat.NotebookNode,
    *,
    config: Config | Mapping[str, Any] | str | Path | None = None,
    target: str = "substack",
    execute: bool = False,
    working_dir: str | Path | None = None,
) -> str:
    """Convert an input notebook/document into platform-ready HTML.

    Args:
        notebook: In-memory content payload as one of:
            - Markdown/Quarto text string
            - Jupyter notebook payload (dict/NotebookNode)
            - text payload mapping:
                ``{"format": "md"|"qmd", "content": "<document text>"}``
        config: Conversion config as one of:
            - ``None`` (use defaults)
            - ``Config`` instance
            - dict-like mapping using the same schema as ``config.yaml``
            - path to a YAML config file
        target: Platform target name (``substack``, ``medium``, ``x``).
        execute: Whether to execute code cells before rendering.
        working_dir: Execution working directory for in-memory payloads.
            Defaults to current working directory.

    Returns:
        Full HTML page ready for the selected target.
    """
    resolved_config = _resolve_config(config)
    resolved_config = apply_platform_defaults(resolved_config, target)
    builder = get_builder(target)
    converter = Converter(resolved_config, execute=execute)

    notebook_node = _coerce_api_payload(notebook)
    content_html = converter.convert_notebook(
        notebook_node,
        cwd=_resolve_working_dir(working_dir),
    )
    return builder.build_page(content_html)


def supported_targets() -> list[str]:
    """Return supported target platform names."""
    return list_platforms()


def load_input_payload(path_like: str | Path) -> Mapping[str, Any] | nbformat.NotebookNode:
    """Load a supported input path into an in-memory payload consumable by ``convert``."""
    path = _sanitize_input_path(path_like)
    suffix = path.suffix.lower()
    if suffix == ".ipynb":
        return _read_ipynb_payload(path)
    if suffix == ".md":
        return _text_payload_from_path(path, fmt="md")
    return _text_payload_from_path(path, fmt="qmd")


def load_notebook_payload(path_like: str | Path) -> nbformat.NotebookNode:
    """Load an ``.ipynb`` file into a validated in-memory notebook payload."""
    path = _sanitize_input_path(path_like, allowed_suffixes=_IPYNB_SUFFIXES)
    return _read_ipynb_payload(path)


def load_markdown_payload(path_like: str | Path) -> Mapping[str, str]:
    """Load a Markdown file into a text payload mapping consumable by ``convert``."""
    path = _sanitize_input_path(path_like, allowed_suffixes=_MD_SUFFIXES)
    return _text_payload_from_path(path, fmt="md")


def load_quarto_payload(path_like: str | Path) -> Mapping[str, str]:
    """Load a Quarto file into a text payload mapping consumable by ``convert``."""
    path = _sanitize_input_path(path_like, allowed_suffixes=_QMD_SUFFIXES)
    return _text_payload_from_path(path, fmt="qmd")


def _resolve_config(
    config: Config | Mapping[str, Any] | str | Path | None,
) -> Config:
    if config is None:
        return Config()
    if isinstance(config, Config):
        return config
    if isinstance(config, Mapping):
        return load_config_from_dict(config)
    if isinstance(config, (str, Path)):
        return load_config(Path(config))
    raise TypeError(
        "config must be None, Config, dict-like mapping, or a config file path."
    )


def _sanitize_input_path(
    path_like: str | Path,
    *,
    allowed_suffixes: frozenset[str] | None = None,
) -> Path:
    raw = str(path_like)
    if _CONTROL_CHAR_RE.search(raw):
        raise ValueError("input path contains invalid control characters")

    path = Path(path_like)
    suffix = path.suffix.lower()
    suffixes = allowed_suffixes or _ALLOWED_INPUT_SUFFIXES
    if suffix not in suffixes:
        allowed = ", ".join(sorted(suffixes))
        raise ValueError(f"input path must use one of: {allowed}")
    if not path.exists():
        raise FileNotFoundError(f"input path '{path}' not found.")
    if not path.is_file():
        raise ValueError(f"input path '{path}' must be a file.")
    return path


def _coerce_api_payload(
    notebook: str | Mapping[str, Any] | nbformat.NotebookNode,
) -> nbformat.NotebookNode:
    if isinstance(notebook, Path):
        raise TypeError(
            "convert() accepts in-memory content payloads only. "
            "Use load_input_payload(path) to read files first."
        )

    if isinstance(notebook, str):
        if _looks_like_supported_path(notebook):
            raise TypeError(
                "convert() accepts in-memory content payloads only. "
                "Use load_input_payload(path) to read files first."
            )
        return _coerce_text_string_payload(notebook)

    text_node = _coerce_text_mapping_payload(notebook)
    if text_node is not None:
        return text_node
    return _coerce_notebook_node(notebook)


def _coerce_notebook_node(
    notebook: Mapping[str, Any] | nbformat.NotebookNode,
) -> nbformat.NotebookNode:
    """Normalize and validate an in-memory notebook payload."""
    if isinstance(notebook, nbformat.NotebookNode):
        node = deepcopy(notebook)
    elif isinstance(notebook, Mapping):
        node = nbformat.from_dict(deepcopy(dict(notebook)))
    else:
        raise TypeError(
            "notebook must be an in-memory payload: markdown/quarto string, "
            "text payload mapping, or Jupyter notebook dict/NotebookNode."
        )

    # Normalization for common real-world payloads:
    # - add cell ids when omitted
    # - add kernelspec.display_name when kernelspec.name exists
    cells = node.get("cells", [])
    if isinstance(cells, list):
        for cell in cells:
            if isinstance(cell, Mapping) and not cell.get("id"):
                cell["id"] = uuid4().hex[:8]

    metadata = node.get("metadata", {})
    if isinstance(metadata, Mapping):
        kernelspec = metadata.get("kernelspec")
        if isinstance(kernelspec, Mapping):
            name = kernelspec.get("name")
            if name and not kernelspec.get("display_name"):
                kernelspec["display_name"] = str(name)

    try:
        nbformat.validate(node)
    except Exception as exc:
        raise ValueError(f"Invalid Jupyter notebook payload: {exc}") from exc
    return node


def _coerce_text_string_payload(text: str) -> nbformat.NotebookNode:
    """Parse raw in-memory Markdown/Quarto text payload."""
    # Quarto chunk fences are the strongest signal for .qmd.
    if _QMD_CHUNK_RE.search(text):
        return read_qmd_text(text)
    return read_md_text(text)


def _coerce_text_mapping_payload(
    notebook: Mapping[str, Any] | nbformat.NotebookNode,
) -> nbformat.NotebookNode | None:
    """Parse explicit in-memory text payload mappings for Markdown/Quarto content."""
    if not isinstance(notebook, Mapping):
        return None

    # Notebook payloads take precedence.
    if "cells" in notebook or "nbformat" in notebook:
        return None

    fmt_raw = notebook.get("format")
    if fmt_raw is None:
        return None
    if not isinstance(fmt_raw, str):
        raise TypeError("In-memory text payload field 'format' must be a string.")

    fmt = _TEXT_PAYLOAD_ALIASES.get(fmt_raw.strip().lower().lstrip("."))
    if fmt is None:
        raise TypeError(
            "In-memory text payload 'format' must be one of: md, markdown, qmd, quarto."
        )

    content = notebook.get("content", notebook.get("source", notebook.get("text")))
    if not isinstance(content, str):
        raise TypeError(
            "In-memory text payload must include string content via 'content' "
            "(or 'source'/'text')."
        )

    if fmt == "qmd":
        return read_qmd_text(content)
    return read_md_text(content)


def _read_ipynb_payload(path: Path) -> nbformat.NotebookNode:
    with path.open("r", encoding="utf-8") as handle:
        notebook = nbformat.read(handle, as_version=4)
    return _coerce_notebook_node(notebook)


def _text_payload_from_path(path: Path, *, fmt: str) -> Mapping[str, str]:
    return {
        "format": fmt,
        "content": path.read_text(encoding="utf-8"),
    }


def _looks_like_supported_path(text: str) -> bool:
    if "\n" in text or "\r" in text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    return Path(stripped).suffix.lower() in _ALLOWED_INPUT_SUFFIXES


def _resolve_working_dir(path_like: str | Path | None) -> Path:
    """Resolve and validate working directory for in-memory notebook execution."""
    if path_like is None:
        return Path.cwd()

    raw = str(path_like)
    if _CONTROL_CHAR_RE.search(raw):
        raise ValueError("working_dir contains invalid control characters")

    path = Path(path_like)
    if not path.exists():
        raise FileNotFoundError(f"working_dir '{path}' not found.")
    if not path.is_dir():
        raise ValueError(f"working_dir '{path}' must be a directory.")
    return path.resolve()
