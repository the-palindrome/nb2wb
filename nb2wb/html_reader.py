from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
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
    raw = str(path_like)
    if _CONTROL_CHAR_RE.search(raw):
        raise ValueError("input path contains invalid control characters")

    path = Path(path_like)
    suffix = path.suffix.lower()
    if suffix not in _ALLOWED_HTML_SUFFIXES:
        allowed = ", ".join(sorted(_ALLOWED_HTML_SUFFIXES))
        raise ValueError(f"input path must use one of: {allowed}")
    if not path.exists():
        raise FileNotFoundError(f"input path '{path}' not found.")
    if not path.is_file():
        raise ValueError(f"input path '{path}' must be a file.")
    return path
