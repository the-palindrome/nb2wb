"""Programmatic API for server-side nb2wb usage."""
from __future__ import annotations

from copy import deepcopy
import re
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import nbformat
from nbformat.v4.convert import upgrade_output as _upgrade_v4_output

from .config import (
    Config,
    apply_target_profile_defaults,
    load_config,
    load_config_from_dict,
    resolve_target_options,
)
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
_CANONICAL_NBFORMAT = 4
_CANONICAL_NBFORMAT_MINOR = 5
_CELL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_V4_TOP_LEVEL_KEYS = frozenset({"cells", "metadata", "nbformat", "nbformat_minor"})
_LEGACY_TOP_LEVEL_METADATA_KEYS = ("orig_nbformat", "orig_nbformat_minor")


def convert(
    notebook: str | Mapping[str, Any] | nbformat.NotebookNode,
    *,
    config: Config | Mapping[str, Any] | str | Path | None = None,
    target: str = "default",
    target_options: Mapping[str, Any] | None = None,
    execute: bool = False,
    working_dir: str | Path | None = None,
    raw_mode: bool = False,
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
        target: Platform target name (``default``, ``substack``, ``medium``,
            ``x``, ``linkedin``, ``devto``, ``hashnode``, ``ghost``,
            ``wordpress``).
        target_options: Optional per-target feature overrides (image strategy,
            copy script mode, table mode, article width, etc.).
        execute: Whether to execute code cells before rendering.
        working_dir: Execution working directory for in-memory payloads.
            Defaults to current working directory.
        raw_mode: When True, omit the preview toolbar/header from output HTML.

    Returns:
        Full HTML page ready for the selected target.
    """
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
    converter = Converter(resolved_config, execute=execute)

    notebook_node = _coerce_api_payload(notebook)
    content_html = converter.convert_notebook(
        notebook_node,
        cwd=_resolve_working_dir(working_dir),
    )
    return builder.build_page(content_html, raw_mode=raw_mode)


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
        return _coerce_text_string_payload(notebook)

    text_node = _coerce_text_mapping_payload(notebook)
    if text_node is not None:
        return text_node
    return _coerce_notebook_node(notebook)


def _coerce_notebook_node(
    notebook: Mapping[str, Any] | nbformat.NotebookNode,
) -> nbformat.NotebookNode:
    """Normalize to canonical v4.5 and validate an in-memory notebook payload."""
    if isinstance(notebook, nbformat.NotebookNode):
        node = deepcopy(notebook)
    elif isinstance(notebook, Mapping):
        node = nbformat.from_dict(deepcopy(dict(notebook)))
    else:
        raise TypeError(
            "notebook must be an in-memory payload: markdown/quarto string, "
            "text payload mapping, or Jupyter notebook dict/NotebookNode."
        )

    normalized, repairs = _canonicalize_notebook_payload(node)
    if repairs:
        warnings.warn(
            "Applied notebook compatibility repairs: " + ", ".join(sorted(set(repairs))),
            RuntimeWarning,
            stacklevel=2,
        )
    try:
        nbformat.validate(
            normalized,
            version=_CANONICAL_NBFORMAT,
            version_minor=_CANONICAL_NBFORMAT_MINOR,
        )
    except Exception as exc:
        raise ValueError(
            f"Invalid Jupyter notebook payload (invalid/unrepairable schema fields): {exc}"
        ) from exc
    return normalized


def _canonicalize_notebook_payload(
    node: nbformat.NotebookNode,
) -> tuple[nbformat.NotebookNode, list[str]]:
    repairs: list[str] = []

    _move_legacy_top_level_metadata_fields(node, repairs)
    _coerce_top_level_version_fields(node, repairs)

    if _looks_like_mislabeled_v3_payload(node):
        node["nbformat"] = 3
        if _coerce_int(node.get("nbformat_minor")) is None:
            node["nbformat_minor"] = 0
        repairs.append("reclassified_worksheets_payload_as_nbformat_v3")

    major = _coerce_int(node.get("nbformat"))
    if major is None:
        raise ValueError(
            "Invalid Jupyter notebook payload (ambiguous legacy/malformed structure): "
            "missing or invalid 'nbformat'."
        )
    if major > _CANONICAL_NBFORMAT:
        raise ValueError(
            "Invalid Jupyter notebook payload (unsupported major version): "
            f"nbformat={major} is not supported."
        )
    if major < _CANONICAL_NBFORMAT:
        try:
            node = nbformat.convert(node, _CANONICAL_NBFORMAT)
        except Exception as exc:
            raise ValueError(
                "Invalid Jupyter notebook payload "
                "(ambiguous legacy/malformed structure): "
                f"unable to upgrade nbformat={major} payload: {exc}"
            ) from exc
        repairs.append(f"upgraded_nbformat_v{major}_to_v4")

    _move_legacy_top_level_metadata_fields(node, repairs)
    _repair_v4_payload(node, repairs)
    _normalize_notebook_metadata(node, repairs)
    _normalize_cell_ids(node, repairs)

    if _coerce_int(node.get("nbformat")) != _CANONICAL_NBFORMAT:
        node["nbformat"] = _CANONICAL_NBFORMAT
        repairs.append("set_nbformat_to_v4")
    if _coerce_int(node.get("nbformat_minor")) != _CANONICAL_NBFORMAT_MINOR:
        node["nbformat_minor"] = _CANONICAL_NBFORMAT_MINOR
        repairs.append("set_nbformat_minor_to_v5")

    extra_fields = sorted(key for key in node.keys() if key not in _V4_TOP_LEVEL_KEYS)
    if extra_fields:
        fields = ", ".join(extra_fields)
        raise ValueError(
            "Invalid Jupyter notebook payload (invalid/unrepairable schema fields): "
            f"unsupported top-level fields: {fields}"
        )

    return node, repairs


def _coerce_top_level_version_fields(
    node: nbformat.NotebookNode,
    repairs: list[str],
) -> None:
    major = _coerce_int(node.get("nbformat"))
    if major is not None and node.get("nbformat") != major:
        node["nbformat"] = major
        repairs.append("coerced_nbformat_to_integer")

    minor = _coerce_int(node.get("nbformat_minor"))
    if minor is not None and node.get("nbformat_minor") != minor:
        node["nbformat_minor"] = minor
        repairs.append("coerced_nbformat_minor_to_integer")
    if minor is None and "nbformat_minor" in node:
        node["nbformat_minor"] = 0
        repairs.append("defaulted_invalid_nbformat_minor_to_zero")


def _looks_like_mislabeled_v3_payload(node: Mapping[str, Any]) -> bool:
    return (
        _coerce_int(node.get("nbformat")) == 4
        and "cells" not in node
        and isinstance(node.get("worksheets"), list)
    )


def _move_legacy_top_level_metadata_fields(
    node: nbformat.NotebookNode,
    repairs: list[str],
) -> None:
    metadata = node.get("metadata")
    if metadata is None:
        metadata = {}
        node["metadata"] = metadata
    if not isinstance(metadata, Mapping):
        raise ValueError(
            "Invalid Jupyter notebook payload (invalid/unrepairable schema fields): "
            "notebook 'metadata' must be a mapping."
        )

    moved = False
    for key in _LEGACY_TOP_LEVEL_METADATA_KEYS:
        if key in node:
            if key not in metadata:
                metadata[key] = node[key]
            del node[key]
            moved = True
    if moved:
        repairs.append("moved_legacy_orig_nbformat_fields_into_metadata")


def _repair_v4_payload(
    node: nbformat.NotebookNode,
    repairs: list[str],
) -> None:
    if _coerce_int(node.get("nbformat")) != _CANONICAL_NBFORMAT:
        raise ValueError(
            "Invalid Jupyter notebook payload (ambiguous legacy/malformed structure): "
            "failed to normalize payload to nbformat 4."
        )

    if "metadata" not in node:
        node["metadata"] = {}
        repairs.append("added_missing_notebook_metadata")
    metadata = node.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError(
            "Invalid Jupyter notebook payload (invalid/unrepairable schema fields): "
            "notebook 'metadata' must be a mapping."
        )

    if "cells" not in node:
        node["cells"] = []
        repairs.append("added_missing_cells_list")
    cells = node.get("cells")
    if not isinstance(cells, list):
        raise ValueError(
            "Invalid Jupyter notebook payload (invalid/unrepairable schema fields): "
            "'cells' must be a list."
        )

    for idx, cell in enumerate(cells):
        if not isinstance(cell, Mapping):
            raise ValueError(
                "Invalid Jupyter notebook payload (invalid/unrepairable schema fields): "
                f"cell {idx} must be an object."
            )
        _repair_cell(cell, idx, repairs)


def _repair_cell(cell: Mapping[str, Any], idx: int, repairs: list[str]) -> None:
    if "metadata" not in cell:
        cell["metadata"] = {}
        repairs.append("added_missing_cell_metadata")
    metadata = cell.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError(
            "Invalid Jupyter notebook payload (invalid/unrepairable schema fields): "
            f"cell {idx} metadata must be a mapping."
        )

    cell_type = cell.get("cell_type")
    if "source" not in cell:
        if cell_type == "code" and "input" in cell:
            cell["source"] = cell.pop("input")
            repairs.append("mapped_code_input_to_source")
        else:
            cell["source"] = ""
            repairs.append("added_missing_cell_source")
    elif cell_type == "code" and "input" in cell and cell.get("input") == cell.get("source"):
        cell.pop("input")
        repairs.append("removed_redundant_legacy_code_input_field")

    if cell_type != "code":
        return

    if "execution_count" not in cell:
        if "prompt_number" in cell:
            cell["execution_count"] = cell.pop("prompt_number")
            repairs.append("mapped_prompt_number_to_execution_count")
        else:
            cell["execution_count"] = None
            repairs.append("added_missing_execution_count")
    elif "prompt_number" in cell and cell.get("prompt_number") == cell.get("execution_count"):
        cell.pop("prompt_number")
        repairs.append("removed_redundant_legacy_prompt_number_field")

    if "outputs" not in cell:
        cell["outputs"] = []
        repairs.append("added_missing_code_outputs")
    outputs = cell.get("outputs")
    if not isinstance(outputs, list):
        raise ValueError(
            "Invalid Jupyter notebook payload (invalid/unrepairable schema fields): "
            f"cell {idx} outputs must be a list."
        )
    for out_idx, output in enumerate(outputs):
        if not isinstance(output, Mapping):
            raise ValueError(
                "Invalid Jupyter notebook payload (invalid/unrepairable schema fields): "
                f"cell {idx} output {out_idx} must be an object."
            )
        _repair_legacy_output(output, idx, out_idx, repairs)


def _repair_legacy_output(
    output: Mapping[str, Any],
    cell_idx: int,
    out_idx: int,
    repairs: list[str],
) -> None:
    output_type = output.get("output_type")
    if output_type == "stream":
        if "name" not in output and "stream" in output:
            output["name"] = output.pop("stream")
            repairs.append("mapped_stream_output_stream_to_name")
        elif "stream" in output and output.get("stream") == output.get("name"):
            output.pop("stream")
            repairs.append("removed_redundant_stream_output_stream_field")
        return

    if output_type == "pyerr":
        output["output_type"] = "error"
        repairs.append("mapped_output_type_pyerr_to_error")
        return

    if output_type != "pyout":
        return

    try:
        upgraded = _upgrade_v4_output(nbformat.from_dict(deepcopy(dict(output))))
    except Exception as exc:
        raise ValueError(
            "Invalid Jupyter notebook payload (ambiguous legacy/malformed structure): "
            f"unable to upgrade legacy output in cell {cell_idx}, output {out_idx}: {exc}"
        ) from exc

    output.clear()
    output.update(upgraded)
    repairs.append("mapped_output_type_pyout_to_execute_result")


def _normalize_notebook_metadata(node: nbformat.NotebookNode, repairs: list[str]) -> None:
    metadata = node.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError(
            "Invalid Jupyter notebook payload (invalid/unrepairable schema fields): "
            "notebook 'metadata' must be a mapping."
        )
    kernelspec = metadata.get("kernelspec")
    if isinstance(kernelspec, Mapping):
        name = kernelspec.get("name")
        if name and not kernelspec.get("display_name"):
            kernelspec["display_name"] = str(name)
            repairs.append("filled_kernelspec_display_name")


def _normalize_cell_ids(node: nbformat.NotebookNode, repairs: list[str]) -> None:
    cells = node.get("cells", [])
    if not isinstance(cells, list):
        return

    changed = 0
    used: set[str] = set()
    for idx, cell in enumerate(cells):
        if not isinstance(cell, Mapping):
            continue
        raw_id = cell.get("id")
        is_valid_id = (
            isinstance(raw_id, str)
            and _CELL_ID_RE.fullmatch(raw_id) is not None
            and raw_id not in used
        )
        if is_valid_id:
            used.add(raw_id)
            continue

        new_id = _make_deterministic_cell_id(idx, used)
        cell["id"] = new_id
        used.add(new_id)
        changed += 1

    if changed:
        repairs.append(f"normalized_cell_ids:{changed}")


def _make_deterministic_cell_id(idx: int, used: set[str]) -> str:
    base = f"cell-{idx + 1:04d}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
        notebook = nbformat.read(handle, as_version=nbformat.NO_CONVERT)
    return _coerce_notebook_node(notebook)


def _text_payload_from_path(path: Path, *, fmt: str) -> Mapping[str, str]:
    return {
        "format": fmt,
        "content": path.read_text(encoding="utf-8"),
    }


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
