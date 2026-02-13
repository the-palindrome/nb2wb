"""
Convert inline LaTeX ($...$) to Unicode text using the unicodeit library.
"""
from __future__ import annotations

import re

# Match $...$ but NOT $$...$$  (negative look-behind/ahead for $)
_INLINE_RE = re.compile(r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)", re.DOTALL)


def convert_inline_math(text: str) -> str:
    """Replace every $...$ span with its Unicode equivalent."""
    return _INLINE_RE.sub(_replace, text)


def _replace(m: re.Match) -> str:
    latex = m.group(1).strip()
    return _to_unicode(latex)


def _to_unicode(latex: str) -> str:
    try:
        import unicodeit  # optional dependency

        result = unicodeit.replace(latex)
        return result
    except Exception:
        pass
    # Graceful fallback: keep the original delimiters
    return f"${latex}$"
