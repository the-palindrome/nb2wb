from __future__ import annotations

import re
from collections.abc import Collection
from pathlib import Path

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


def _path_from_value(path_like: str | Path, *, label: str) -> Path:
    """Convert a path-like value to ``Path`` after basic input validation."""
    raw = str(path_like)
    if _CONTROL_CHAR_RE.search(raw):
        raise ValueError(f"{label} contains invalid control characters")
    return Path(path_like)


def _validate_suffixes(
    path: Path,
    allowed_suffixes: Collection[str],
    *,
    label: str,
) -> None:
    """Validate that a path uses one of the permitted suffixes."""
    suffix = path.suffix.lower()
    if suffix not in allowed_suffixes:
        allowed = ", ".join(sorted(allowed_suffixes))
        raise ValueError(f"{label} must use one of: {allowed}")


def sanitize_input_file_path(
    path_like: str | Path,
    *,
    allowed_suffixes: Collection[str],
    label: str = "input path",
) -> Path:
    """Validate a path that must reference an existing file."""
    path = _path_from_value(path_like, label=label)
    _validate_suffixes(path, allowed_suffixes, label=label)
    if not path.exists():
        raise FileNotFoundError(f"{label} '{path}' not found.")
    if not path.is_file():
        raise ValueError(f"{label} '{path}' must be a file.")
    return path


def sanitize_optional_cli_path(
    path: Path | None,
    *,
    label: str,
    must_exist: bool = False,
    allowed_suffixes: Collection[str] | None = None,
) -> Path | None:
    """Validate a CLI path argument while preserving CLI-friendly errors."""
    if path is None:
        return None

    sanitized = _path_from_value(path, label=label)
    if allowed_suffixes is not None:
        _validate_suffixes(sanitized, allowed_suffixes, label=label)
    if must_exist and not sanitized.exists():
        raise FileNotFoundError(f"'{sanitized}' not found.")
    return sanitized


def resolve_directory_path(
    path_like: str | Path | None,
    *,
    label: str = "working_dir",
) -> Path:
    """Resolve a directory path that must exist."""
    if path_like is None:
        return Path.cwd()

    path = _path_from_value(path_like, label=label)
    if not path.exists():
        raise FileNotFoundError(f"{label} '{path}' not found.")
    if not path.is_dir():
        raise ValueError(f"{label} '{path}' must be a directory.")
    return path.resolve()
