from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from typing import Literal
from urllib.parse import unquote, urlparse

ImageClassification = Literal["code", "latex", "table", "other"]

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
_LATEX_HINTS = ("math", "latex", "equation", "formula")
_CODE_HINTS = ("code", "snippet", "source", "terminal")
_TABLE_HINTS = ("table", "tabular", "dataframe", "grid")


@dataclass(frozen=True)
class ImageCandidate:
    src: str
    alt: str = ""
    title: str = ""
    classes: tuple[str, ...] = ()
    caption: str = ""
    nearby_text: str = ""


class DefaultImageClassifier:
    """Classify images using HTML metadata only."""

    def classify(self, image: ImageCandidate) -> ImageClassification:
        haystack = _classification_haystack(image)
        if any(hint in haystack for hint in _LATEX_HINTS):
            return "latex"
        if any(hint in haystack for hint in _CODE_HINTS):
            return "code"
        if any(hint in haystack for hint in _TABLE_HINTS):
            return "table"
        if infer_supported_language(image) is not None:
            return "code"
        return "other"


def infer_supported_language(image: ImageCandidate) -> str | None:
    """Infer a scaffold-supported language from image metadata."""
    for text in _candidate_texts(image):
        normalized = normalize_supported_language(text)
        if normalized is not None:
            return normalized

        for match in _LANGUAGE_HINT_RE.finditer(text.lower()):
            normalized = normalize_supported_language(match.group(1))
            if normalized is not None:
                return normalized
    return None


def normalize_supported_language(raw: str | None) -> str | None:
    if not raw:
        return None

    cleaned = raw.strip().lower().lstrip(".")
    if cleaned in SUPPORTED_LANGUAGE_ALIASES:
        return SUPPORTED_LANGUAGE_ALIASES[cleaned]

    for token in re.split(r"[^a-z0-9+-]+", cleaned):
        if token in SUPPORTED_LANGUAGE_ALIASES:
            return SUPPORTED_LANGUAGE_ALIASES[token]
    return None


def _classification_haystack(image: ImageCandidate) -> str:
    return " ".join(_candidate_texts(image)).lower()


def _candidate_texts(image: ImageCandidate) -> list[str]:
    filename = _filename_from_src(image.src)
    parts = [
        image.alt,
        image.title,
        image.caption,
        image.nearby_text,
        " ".join(image.classes),
        filename,
    ]
    return [part for part in parts if part]


def _filename_from_src(src: str) -> str:
    if not src:
        return ""
    parsed = urlparse(src)
    path = parsed.path or src
    return unquote(PurePosixPath(path).name)
