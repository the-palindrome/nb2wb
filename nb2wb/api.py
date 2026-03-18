"""Programmatic API for server-side nb2wb usage."""
from __future__ import annotations

import re
from collections.abc import Mapping
import logging
from pathlib import Path
import time
from typing import Any, Callable

import nbformat

from ._logging import verbose_logging
from ._notebook_payload import coerce_notebook_node as _coerce_notebook_node
from ._path_utils import resolve_directory_path, sanitize_input_file_path
from .config import (
    Config,
    apply_target_profile_defaults,
    load_config,
    load_config_from_dict,
    resolve_target_options,
)
from .converter import Converter
from .html_reader import load_html_payload
from .md_reader import read_md_text
from .ocr.base import OCRRequest
from .platforms import get_builder, list_platforms
from .qmd_reader import read_qmd_text
from .reverter import Reverter

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
_HTML_PAYLOAD_ALIASES = {"html", "htm"}
_QMD_CHUNK_RE = re.compile(r"^```\{(\w[\w.-]*)", re.MULTILINE)
logger = logging.getLogger(__name__)


def convert(
    notebook: str | Mapping[str, Any] | nbformat.NotebookNode,
    *,
    config: Config | Mapping[str, Any] | str | Path | None = None,
    target: str = "default",
    target_options: Mapping[str, Any] | None = None,
    execute: bool = False,
    warnings_mode: bool = False,
    working_dir: str | Path | None = None,
    raw_mode: bool = False,
    verbose: bool = False,
) -> str:
    """Convert an input notebook/document into platform-ready HTML."""
    with verbose_logging(verbose):
        started = time.monotonic()
        logger.debug(
            "Starting convert(target=%s, execute=%s, warnings_mode=%s, raw_mode=%s)",
            target,
            execute,
            warnings_mode,
            raw_mode,
        )
        resolved_config = _resolve_config(config)
        resolved_target_options = resolve_target_options(
            resolved_config.target_options,
            target_options,
        )
        resolved_config = apply_target_profile_defaults(
            resolved_config,
            target,
            target_options=resolved_target_options,
        )
        builder = get_builder(target, target_options=resolved_target_options)
        converter = Converter(
            resolved_config,
            execute=execute,
            warnings_mode=warnings_mode,
        )

        notebook_node = _coerce_api_payload(notebook)
        logger.debug(
            "Normalized input payload into NotebookNode with %d cells",
            len(notebook_node.cells),
        )
        content_html = converter.convert_notebook(
            notebook_node,
            cwd=_resolve_working_dir(working_dir),
        )
        rendered_html = builder.build_page(content_html, raw_mode=raw_mode)
        logger.debug(
            "Finished convert() in %.2fs with %d output characters",
            time.monotonic() - started,
            len(rendered_html),
        )
        return rendered_html


def supported_targets() -> list[str]:
    """Return the supported publishing target names."""
    return list_platforms()


def revert(
    document: str | Mapping[str, Any],
    *,
    ocr_pipeline: Callable[[OCRRequest], dict[str, str]] | None = None,
    verbose: bool = False,
) -> nbformat.NotebookNode:
    """Convert an HTML document into a scaffolded Jupyter notebook."""
    with verbose_logging(verbose):
        started = time.monotonic()
        logger.debug("Starting revert()")
        html_document, source_dir = _coerce_html_payload(document)
        notebook = Reverter(
            source_dir=source_dir,
            ocr_pipeline=ocr_pipeline,
        ).revert_html(html_document)
        logger.debug(
            "Finished revert() in %.2fs with %d cells",
            time.monotonic() - started,
            len(notebook.cells),
        )
        return notebook


def load_input_payload(
    path_like: str | Path,
    *,
    verbose: bool = False,
) -> Mapping[str, Any] | nbformat.NotebookNode:
    """Load a supported input file into an in-memory conversion payload."""
    with verbose_logging(verbose):
        path = _sanitize_input_path(path_like)
        suffix = path.suffix.lower()
        logger.debug("Loading input payload from %s", path)
        if suffix == ".ipynb":
            return _read_ipynb_payload(path)
        if suffix == ".md":
            return _text_payload_from_path(path, fmt="md")
        return _text_payload_from_path(path, fmt="qmd")


def load_notebook_payload(
    path_like: str | Path,
    *,
    verbose: bool = False,
) -> nbformat.NotebookNode:
    """Load an ``.ipynb`` file into a validated in-memory notebook payload."""
    with verbose_logging(verbose):
        path = _sanitize_input_path(path_like, allowed_suffixes=_IPYNB_SUFFIXES)
        logger.debug("Loading notebook payload from %s", path)
        return _read_ipynb_payload(path)


def load_markdown_payload(
    path_like: str | Path,
    *,
    verbose: bool = False,
) -> Mapping[str, str]:
    """Load a Markdown file into a text payload mapping for ``convert``."""
    with verbose_logging(verbose):
        path = _sanitize_input_path(path_like, allowed_suffixes=_MD_SUFFIXES)
        logger.debug("Loading markdown payload from %s", path)
        return _text_payload_from_path(path, fmt="md")


def load_quarto_payload(
    path_like: str | Path,
    *,
    verbose: bool = False,
) -> Mapping[str, str]:
    """Load a Quarto file into a text payload mapping for ``convert``."""
    with verbose_logging(verbose):
        path = _sanitize_input_path(path_like, allowed_suffixes=_QMD_SUFFIXES)
        logger.debug("Loading Quarto payload from %s", path)
        return _text_payload_from_path(path, fmt="qmd")


def _resolve_config(
    config: Config | Mapping[str, Any] | str | Path | None,
) -> Config:
    """Normalize API config input into a ``Config`` instance."""
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
    """Validate an input path before loading notebook or text content."""
    return sanitize_input_file_path(
        path_like,
        allowed_suffixes=allowed_suffixes or _ALLOWED_INPUT_SUFFIXES,
        label="input path",
    )


def _coerce_api_payload(
    notebook: str | Mapping[str, Any] | nbformat.NotebookNode,
) -> nbformat.NotebookNode:
    """Convert supported API payload shapes into a notebook model."""
    if isinstance(notebook, Path):
        raise TypeError(
            "convert() accepts in-memory content payloads only. "
            "Use load_input_payload(path) to read files first."
        )

    if isinstance(notebook, str):
        return _coerce_text_string_payload(notebook)

    text_node = _coerce_text_mapping_payload(notebook)
    if text_node is not None:
        return text_node
    return _coerce_notebook_node(notebook)


def _coerce_html_payload(document: str | Mapping[str, Any]) -> tuple[str, Path | None]:
    """Normalize an HTML revert payload and optional source directory."""
    if isinstance(document, Path):
        raise TypeError(
            "revert() accepts in-memory HTML payloads only. "
            "Use load_html_payload(path) to read files first."
        )
    if isinstance(document, str):
        return document, None
    if not isinstance(document, Mapping):
        raise TypeError(
            "document must be an in-memory HTML payload: raw HTML string or "
            "a mapping with format/content fields."
        )

    fmt_raw = document.get("format")
    if not isinstance(fmt_raw, str):
        raise TypeError("In-memory HTML payload field 'format' must be a string.")
    fmt = fmt_raw.strip().lower().lstrip(".")
    if fmt not in _HTML_PAYLOAD_ALIASES:
        raise TypeError("In-memory HTML payload 'format' must be one of: html, htm.")

    content = _read_text_payload_content(document, label="In-memory HTML payload")

    source_dir_raw = document.get("source_dir")
    source_dir: Path | None = None
    if source_dir_raw is not None:
        if not isinstance(source_dir_raw, (str, Path)):
            raise TypeError("In-memory HTML payload field 'source_dir' must be path-like.")
        source_dir = _resolve_working_dir(source_dir_raw)
    return content, source_dir


def _coerce_text_string_payload(text: str) -> nbformat.NotebookNode:
    """Parse raw in-memory Markdown or Quarto text into a notebook."""
    if _QMD_CHUNK_RE.search(text):
        return read_qmd_text(text)
    return read_md_text(text)


def _coerce_text_mapping_payload(
    notebook: Mapping[str, Any] | nbformat.NotebookNode,
) -> nbformat.NotebookNode | None:
    """Parse explicit text payload mappings for Markdown or Quarto content."""
    if not isinstance(notebook, Mapping):
        return None

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

    content = _read_text_payload_content(notebook, label="In-memory text payload")
    if fmt == "qmd":
        return read_qmd_text(content)
    return read_md_text(content)


def _read_ipynb_payload(path: Path) -> nbformat.NotebookNode:
    """Read and normalize a notebook file from disk."""
    with path.open("r", encoding="utf-8") as handle:
        notebook = nbformat.read(handle, as_version=nbformat.NO_CONVERT)
    return _coerce_notebook_node(notebook)


def _text_payload_from_path(path: Path, *, fmt: str) -> Mapping[str, str]:
    """Build an in-memory text payload mapping from a file path."""
    return {
        "format": fmt,
        "content": path.read_text(encoding="utf-8"),
    }


def _resolve_working_dir(path_like: str | Path | None) -> Path:
    """Resolve and validate the working directory for notebook execution."""
    return resolve_directory_path(path_like, label="working_dir")


def _read_text_payload_content(payload: Mapping[str, Any], *, label: str) -> str:
    """Read the string content field shared by in-memory text payloads."""
    content = payload.get("content", payload.get("source", payload.get("text")))
    if not isinstance(content, str):
        raise TypeError(
            f"{label} must include string content via 'content' (or 'source'/'text')."
        )
    return content
