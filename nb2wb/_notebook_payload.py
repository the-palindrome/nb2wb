"""Notebook payload normalization for the public conversion API."""
from __future__ import annotations

from copy import deepcopy
import re
import warnings
from collections.abc import Mapping, MutableMapping
from typing import Any

import nbformat
from nbformat.v4.convert import upgrade_output as _upgrade_v4_output

_CANONICAL_NBFORMAT = 4
_CANONICAL_NBFORMAT_MINOR = 5
_CELL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_V4_TOP_LEVEL_KEYS = frozenset({"cells", "metadata", "nbformat", "nbformat_minor"})
_LEGACY_TOP_LEVEL_METADATA_KEYS = ("orig_nbformat", "orig_nbformat_minor")


def coerce_notebook_node(
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
    """Repair a notebook payload into canonical nbformat v4.5 form."""
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
    node: MutableMapping[str, Any],
    repairs: list[str],
) -> None:
    """Normalize top-level nbformat version fields to integers."""
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
    """Detect legacy worksheet notebooks mislabeled as nbformat 4."""
    return (
        _coerce_int(node.get("nbformat")) == 4
        and "cells" not in node
        and isinstance(node.get("worksheets"), list)
    )


def _move_legacy_top_level_metadata_fields(
    node: MutableMapping[str, Any],
    repairs: list[str],
) -> None:
    """Move legacy nbformat metadata fields under ``metadata``."""
    metadata = node.get("metadata")
    if metadata is None:
        metadata = {}
        node["metadata"] = metadata
    if not isinstance(metadata, MutableMapping):
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
    node: MutableMapping[str, Any],
    repairs: list[str],
) -> None:
    """Ensure a v4 notebook has the fields required by nbformat."""
    if _coerce_int(node.get("nbformat")) != _CANONICAL_NBFORMAT:
        raise ValueError(
            "Invalid Jupyter notebook payload (ambiguous legacy/malformed structure): "
            "failed to normalize payload to nbformat 4."
        )

    if "metadata" not in node:
        node["metadata"] = {}
        repairs.append("added_missing_notebook_metadata")
    metadata = node.get("metadata")
    if not isinstance(metadata, MutableMapping):
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
        if not isinstance(cell, MutableMapping):
            raise ValueError(
                "Invalid Jupyter notebook payload (invalid/unrepairable schema fields): "
                f"cell {idx} must be an object."
            )
        _repair_cell(cell, idx, repairs)


def _repair_cell(
    cell: MutableMapping[str, Any],
    idx: int,
    repairs: list[str],
) -> None:
    """Repair one notebook cell to match the nbformat v4 schema."""
    if "metadata" not in cell:
        cell["metadata"] = {}
        repairs.append("added_missing_cell_metadata")
    metadata = cell.get("metadata")
    if not isinstance(metadata, MutableMapping):
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
        if not isinstance(output, MutableMapping):
            raise ValueError(
                "Invalid Jupyter notebook payload (invalid/unrepairable schema fields): "
                f"cell {idx} output {out_idx} must be an object."
            )
        _repair_legacy_output(output, idx, out_idx, repairs)


def _repair_legacy_output(
    output: MutableMapping[str, Any],
    cell_idx: int,
    out_idx: int,
    repairs: list[str],
) -> None:
    """Upgrade legacy code-cell output records to modern v4 structure."""
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


def _normalize_notebook_metadata(
    node: MutableMapping[str, Any],
    repairs: list[str],
) -> None:
    """Fill missing notebook metadata fields that have safe defaults."""
    metadata = node.get("metadata")
    if not isinstance(metadata, MutableMapping):
        raise ValueError(
            "Invalid Jupyter notebook payload (invalid/unrepairable schema fields): "
            "notebook 'metadata' must be a mapping."
        )
    kernelspec = metadata.get("kernelspec")
    if isinstance(kernelspec, MutableMapping):
        name = kernelspec.get("name")
        if name and not kernelspec.get("display_name"):
            kernelspec["display_name"] = str(name)
            repairs.append("filled_kernelspec_display_name")


def _normalize_cell_ids(
    node: MutableMapping[str, Any],
    repairs: list[str],
) -> None:
    """Ensure every notebook cell has a unique, valid cell identifier."""
    cells = node.get("cells", [])
    if not isinstance(cells, list):
        return

    changed = 0
    used: set[str] = set()
    for idx, cell in enumerate(cells):
        if not isinstance(cell, MutableMapping):
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
    """Generate a repeatable cell ID that does not collide with prior IDs."""
    base = f"cell-{idx + 1:04d}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _coerce_int(value: Any) -> int | None:
    """Attempt to coerce a value to ``int`` without raising errors."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
