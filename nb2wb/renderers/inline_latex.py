"""
Convert inline LaTeX ($...$) to Unicode/HTML.

Pipeline for each $...$ span:
  1. Expand \\frac{num}{den} → (num)/(den)  (handles nested braces)
  2. Convert known commands to Unicode via unicodeit
  3. Convert any remaining ^{...} / _{...} to Unicode superscripts/subscripts,
     falling back to <sup>/<sub> tags when the characters have no Unicode form
  4. Strip leftover bare braces
  5. Wrap single-letter Latin variables and Greek letters in <em>
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Top-level pattern: $...$ but NOT $$...$$
# ---------------------------------------------------------------------------
_INLINE_RE = re.compile(r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)", re.DOTALL)

# ---------------------------------------------------------------------------
# Unicode superscript / subscript maps
# ---------------------------------------------------------------------------
_SUPERSCRIPT: dict[str, str] = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ",
    "f": "ᶠ", "g": "ᵍ", "h": "ʰ", "i": "ⁱ", "j": "ʲ",
    "k": "ᵏ", "l": "ˡ", "m": "ᵐ", "n": "ⁿ", "o": "ᵒ",
    "p": "ᵖ", "r": "ʳ", "s": "ˢ", "t": "ᵗ", "u": "ᵘ",
    "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ",
}
_TO_SUP = str.maketrans(_SUPERSCRIPT)

_SUBSCRIPT: dict[str, str] = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "k": "ₖ", "l": "ₗ",
    "m": "ₘ", "n": "ₙ", "o": "ₒ", "p": "ₚ", "s": "ₛ",
    "t": "ₜ", "x": "ₓ",
}
_TO_SUB = str.maketrans(_SUBSCRIPT)

# Greek letters (and math-variant forms) that LaTeX italicises in math mode
_GREEK = (
    "αβγδεζηθικλμνξοπρστυφχψω"
    "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
    "ϕϵϑϱϖϰ"   # \phi, \epsilon, \vartheta, \varrho, \varpi, \varkappa
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def convert_inline_math(text: str) -> str:
    """Replace every $...$ span with its Unicode/HTML equivalent."""
    return _INLINE_RE.sub(lambda m: _to_unicode(m.group(1).strip()), text)


# ---------------------------------------------------------------------------
# Conversion pipeline
# ---------------------------------------------------------------------------

def _to_unicode(latex: str) -> str:
    """Convert a single inline LaTeX expression to Unicode/HTML text."""
    latex = _expand_frac(latex)

    try:
        import unicodeit
    except ImportError:
        result = latex
    else:
        try:
            result = unicodeit.replace(latex)
        except (TypeError, ValueError):
            result = latex
        except Exception:
            # unicodeit internals can raise parser-specific exceptions for
            # malformed input; keep conversion best-effort.
            result = latex

    if not isinstance(result, str):
        result = latex

    result = _expand_scripts(result)
    result = result.replace("{", "").replace("}", "")
    result = _italicize(result)
    return result


# ---------------------------------------------------------------------------
# Step 1 – \frac expansion (brace-depth aware)
# ---------------------------------------------------------------------------

def _brace_arg(s: str, pos: int) -> tuple[str, int]:
    """Return (content, end_pos) of the brace group starting at pos."""
    if pos >= len(s) or s[pos] != "{":
        return (s[pos : pos + 1], pos + 1)
    depth = 0
    for i in range(pos, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return (s[pos + 1 : i], i + 1)
    return (s[pos + 1 :], len(s))


def _expand_frac(latex: str) -> str:
    """Replace \\frac{num}{den} with (num)/(den)."""
    result: list[str] = []
    i = 0
    while i < len(latex):
        if latex[i : i + 5] == r"\frac":
            i += 5
            while i < len(latex) and latex[i] == " ":
                i += 1
            num, i = _brace_arg(latex, i)
            while i < len(latex) and latex[i] == " ":
                i += 1
            den, i = _brace_arg(latex, i)
            result.append(f"({num})/({den})")
        else:
            result.append(latex[i])
            i += 1
    return "".join(result)


# ---------------------------------------------------------------------------
# Step 3 – superscript / subscript expansion
# ---------------------------------------------------------------------------

def _script_html(inner: str, table: dict, tag: str) -> str:
    """Map inner to Unicode script chars; fall back to an HTML tag."""
    mapped = inner.translate(str.maketrans(table))
    if mapped != inner and all(
        mapped[j] != inner[j] for j in range(len(inner)) if inner[j].strip()
    ):
        return mapped
    return f"<{tag}>{inner}</{tag}>"


def _expand_scripts(text: str) -> str:
    """Convert remaining ^{...} and _{...} to Unicode or <sup>/<sub>."""
    text = re.sub(
        r"\^\{([^}]*)\}",
        lambda m: _script_html(m.group(1), _SUPERSCRIPT, "sup"),
        text,
    )
    text = re.sub(
        r"_\{([^}]*)\}",
        lambda m: _script_html(m.group(1), _SUBSCRIPT, "sub"),
        text,
    )
    # Bare ^x / _x (single character, no braces)
    text = re.sub(
        r"\^([^\s{])",
        lambda m: m.group(1).translate(_TO_SUP),
        text,
    )
    text = re.sub(
        r"_([^\s{])",
        lambda m: m.group(1).translate(_TO_SUB),
        text,
    )
    return text


# ---------------------------------------------------------------------------
# Step 5 – italicise variables
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _italicize(text: str) -> str:
    """Wrap single-letter Latin variables and Greek letters in <em>."""
    parts = _HTML_TAG_RE.split(text)
    tags = _HTML_TAG_RE.findall(text)
    processed: list[str] = []
    for k, part in enumerate(parts):
        # Single standalone Latin letters
        part = re.sub(r"(?<![A-Za-z])([A-Za-z])(?![A-Za-z])", r"<em>\1</em>", part)
        # Greek letters
        part = re.sub(f"[{_GREEK}]", lambda m: f"<em>{m.group(0)}</em>", part)
        processed.append(part)
        if k < len(tags):
            processed.append(tags[k])
    return "".join(processed)
