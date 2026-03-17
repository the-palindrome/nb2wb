from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ._path_utils import sanitize_input_file_path

_ALLOWED_HTML_SUFFIXES = frozenset({".html", ".htm"})


def load_html_payload(path_like: str | Path) -> Mapping[str, str]:
    """Load an HTML document into an in-memory payload for ``revert``.

    Args:
        path_like: Path to the HTML file on disk.

    Returns:
        A mapping containing HTML content and its source directory.
    """
    path = _sanitize_html_path(path_like)
    return {
        "format": "html",
        "content": path.read_text(encoding="utf-8"),
        "source_dir": str(path.parent.resolve()),
    }


def _sanitize_html_path(path_like: str | Path) -> Path:
    """Validate an HTML input path before loading it into memory.

    Args:
        path_like: Candidate path supplied by the caller.

    Returns:
        A validated ``Path`` pointing to an existing HTML file.
    """
    return sanitize_input_file_path(
        path_like,
        allowed_suffixes=_ALLOWED_HTML_SUFFIXES,
        label="input path",
    )
