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
_TEXT_PAYLOAD_ALIASES: dict[str, str] = {
    "md": "md",
    "markdown": "md",
    "qmd": "qmd",
    "quarto": "qmd",
}
_QMD_CHUNK_RE = re.compile(r"^```\{(\w[\w.-]*)", re.MULTILINE)


def convert(
    notebook: str | Path | Mapping[str, Any] | nbformat.NotebookNode,
    *,
    config: Config | Mapping[str, Any] | str | Path | None = None,
    target: str = "substack",
    execute: bool = False,
    working_dir: str | Path | None = None,
) -> str:
    """Convert an input notebook/document into platform-ready HTML.

    Args:
        notebook: Either:
            - path to an ``.ipynb``, ``.qmd``, or ``.md`` file, or
            - in-memory Markdown/Quarto text (string), or
            - in-memory Jupyter notebook payload (dict/NotebookNode), or
            - in-memory text payload mapping:
                ``{"format": "md"|"qmd", "content": "<document text>"}``
        config: Conversion config as one of:
            - ``None`` (use defaults)
            - ``Config`` instance
            - dict-like mapping using the same schema as ``config.yaml``
            - path to a YAML config file
        target: Platform target name (``substack``, ``medium``, ``x``).
        execute: Whether to execute code cells before rendering.
        working_dir: Execution working directory for in-memory notebook payloads.
            Defaults to current working directory. Ignored for path inputs.

    Returns:
        Full HTML page ready for the selected target.
    """
    resolved_config = _resolve_config(config)
    resolved_config = apply_platform_defaults(resolved_config, target)
    builder = get_builder(target)
    converter = Converter(resolved_config, execute=execute)

    if isinstance(notebook, Path):
        notebook_path = _sanitize_input_path(notebook)
        content_html = converter.convert(notebook_path)
    elif isinstance(notebook, str):
        text_node = _coerce_text_string_payload(notebook)
        if text_node is not None:
            content_html = converter.convert_notebook(
                text_node,
                cwd=_resolve_working_dir(working_dir),
            )
        else:
            notebook_path = _sanitize_input_path(notebook)
            content_html = converter.convert(notebook_path)
    else:
        text_node = _coerce_text_mapping_payload(notebook)
        notebook_node = text_node if text_node is not None else _coerce_notebook_node(notebook)
        content_html = converter.convert_notebook(
            notebook_node,
            cwd=_resolve_working_dir(working_dir),
        )
    return builder.build_page(content_html)


def supported_targets() -> list[str]:
    """Return supported target platform names."""
    return list_platforms()


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


def _sanitize_input_path(path_like: str | Path) -> Path:
    raw = str(path_like)
    if _CONTROL_CHAR_RE.search(raw):
        raise ValueError("notebook path contains invalid control characters")

    path = Path(path_like)
    suffix = path.suffix.lower()
    if suffix not in _ALLOWED_INPUT_SUFFIXES:
        allowed = ", ".join(sorted(_ALLOWED_INPUT_SUFFIXES))
        raise ValueError(f"notebook path must use one of: {allowed}")
    if not path.exists():
        raise FileNotFoundError(f"'{path}' not found.")
    return path


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
            "notebook must be a path or an in-memory Jupyter notebook "
            "payload (dict/NotebookNode)."
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


def _coerce_text_string_payload(text: str) -> nbformat.NotebookNode | None:
    """Parse raw in-memory Markdown/Quarto text when the input is clearly not a path."""
    # Keep existing path behavior for one-line strings.
    if "\n" not in text and "\r" not in text:
        return None

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
