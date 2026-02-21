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
from .platforms import get_builder, list_platforms

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_ALLOWED_INPUT_SUFFIXES = frozenset({".ipynb", ".qmd", ".md"})


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
            - in-memory Jupyter notebook payload (dict/NotebookNode)
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

    if isinstance(notebook, (str, Path)):
        notebook_path = _sanitize_input_path(notebook)
        content_html = converter.convert(notebook_path)
    else:
        notebook_node = _coerce_notebook_node(notebook)
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
