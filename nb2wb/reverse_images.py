from __future__ import annotations

import re
from typing import Iterable

SUPPORTED_LANGUAGE_ALIASES: dict[str, str] = {
    "python": "python",
    "py": "python",
    "r": "r",
    "julia": "julia",
    "jl": "julia",
    "bash": "bash",
    "sh": "bash",
    "shell": "bash",
    "zsh": "bash",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "sql": "sql",
}

_LANGUAGE_HINT_RE = re.compile(r"\b([a-z][a-z0-9+-]{0,30})\b")


def infer_supported_language_from_parts(parts: Iterable[str]) -> str | None:
    """Infer a supported notebook language from free-form text hints.

    Args:
        parts: Iterable of metadata strings to inspect for language names.

    Returns:
        A normalized supported language name, or ``None`` when unresolved.
    """
    for text in parts:
        normalized = normalize_supported_language(text)
        if normalized is not None:
            return normalized

        for match in _LANGUAGE_HINT_RE.finditer(text.lower()):
            normalized = normalize_supported_language(match.group(1))
            if normalized is not None:
                return normalized
    return None


def normalize_supported_language(raw: str | None) -> str | None:
    """Map free-form language labels onto the supported scaffold set.

    Args:
        raw: Candidate language label extracted from text or metadata.

    Returns:
        A normalized language name, or ``None`` when no match is found.
    """
    if not raw:
        return None

    cleaned = raw.strip().lower().lstrip(".")
    if cleaned in SUPPORTED_LANGUAGE_ALIASES:
        return SUPPORTED_LANGUAGE_ALIASES[cleaned]

    for token in re.split(r"[^a-z0-9+-]+", cleaned):
        if token in SUPPORTED_LANGUAGE_ALIASES:
            return SUPPORTED_LANGUAGE_ALIASES[token]
    return None
