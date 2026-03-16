"""HTML/SVG sanitization helpers for server-safe conversion mode."""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_CSS_DANGEROUS_RE = re.compile(
    r"expression\s*\(|javascript\s*:|vbscript\s*:|-moz-binding",
    re.IGNORECASE,
)
_CSS_IMPORT_RE = re.compile(r"@import\s+[^;]+;?", re.IGNORECASE)
_CSS_URL_RE = re.compile(r"url\((.*?)\)", re.IGNORECASE | re.DOTALL)

_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "meta", "param", "source"}
)
_DROP_WITH_CONTENT = frozenset({"script", "iframe", "object", "embed"})

_HTML_ALLOWED_TAGS = frozenset(
    {
        "a",
        "abbr",
        "b",
        "blockquote",
        "br",
        "code",
        "del",
        "details",
        "div",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "img",
        "kbd",
        "li",
        "ol",
        "p",
        "pre",
        "s",
        "span",
        "strong",
        "sub",
        "summary",
        "sup",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
        "style",
    }
)

_HTML_GLOBAL_ATTRS = frozenset({"class", "id", "title", "role", "dir", "lang", "style"})
_HTML_TAG_ATTRS: dict[str, frozenset[str]] = {
    "a": frozenset({"href", "target", "rel"}),
    "img": frozenset({"src", "alt", "width", "height", "loading", "decoding"}),
    "td": frozenset({"colspan", "rowspan"}),
    "th": frozenset({"colspan", "rowspan"}),
}

_SVG_ALLOWED_TAGS = frozenset(
    {
        "svg",
        "g",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "text",
        "tspan",
        "defs",
        "symbol",
        "use",
        "clippath",
        "mask",
        "lineargradient",
        "radialgradient",
        "stop",
        "pattern",
        "marker",
        "title",
        "desc",
        "image",
        "style",
    }
)

_URI_ATTRS = frozenset({"href", "src", "xlink:href"})
_ALLOWED_DATA_IMAGE_PREFIXES = (
    "data:image/png;base64,",
    "data:image/jpeg;base64,",
    "data:image/gif;base64,",
    "data:image/svg+xml;base64,",
    "data:image/webp;base64,",
    "data:image/bmp;base64,",
    "data:image/tiff;base64,",
)


def sanitize_fragment(
    fragment: str,
    *,
    profile: str = "html",
) -> str:
    """Sanitize an HTML or SVG fragment using a parser-based allowlist.

    Args:
        fragment: HTML or SVG fragment to sanitize.
        profile: Sanitizer profile name, either ``html`` or ``svg``.

    Returns:
        Sanitized markup with unsafe content removed.
    """
    parser = _FragmentSanitizer(profile=profile)
    parser.feed(fragment)
    parser.close()
    return parser.html


class _FragmentSanitizer(HTMLParser):
    """Streaming sanitizer for HTML fragments."""

    def __init__(self, *, profile: str) -> None:
        """Initialize a streaming sanitizer for HTML or SVG fragments.

        Args:
            profile: Sanitizer profile name, either ``html`` or ``svg``.

        Returns:
            ``None``. Internal parser state is initialized.
        """
        super().__init__(convert_charrefs=False)
        if profile not in {"html", "svg"}:
            raise ValueError(f"Unknown sanitizer profile: {profile}")
        self._profile = profile
        self._parts: list[str] = []
        self._drop_depth = 0
        self._style_depth = 0

    @property
    def html(self) -> str:
        """Return the sanitized fragment accumulated so far.

        Args:
            None.

        Returns:
            The sanitized HTML or SVG fragment as a string.
        """
        return "".join(self._parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle an opening HTML tag during sanitization.

        Args:
            tag: Raw tag name encountered by the parser.
            attrs: Raw attributes attached to the tag.

        Returns:
            ``None``. Sanitized output is appended internally.
        """
        lname = tag.lower()
        if lname in _DROP_WITH_CONTENT:
            self._drop_depth += 1
            return
        if self._drop_depth:
            return
        if not _is_allowed_tag(lname, self._profile):
            return
        clean_attrs = _sanitize_attrs(lname, attrs, self._profile)
        self._parts.append(_start_tag(lname, clean_attrs))
        if lname == "style":
            self._style_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle a self-closing HTML tag during sanitization.

        Args:
            tag: Raw tag name encountered by the parser.
            attrs: Raw attributes attached to the tag.

        Returns:
            ``None``. Sanitized output is appended internally.
        """
        lname = tag.lower()
        if lname in _DROP_WITH_CONTENT or self._drop_depth:
            return
        if not _is_allowed_tag(lname, self._profile):
            return
        clean_attrs = _sanitize_attrs(lname, attrs, self._profile)
        self._parts.append(_self_closing_tag(lname, clean_attrs))

    def handle_endtag(self, tag: str) -> None:
        """Handle a closing HTML tag during sanitization.

        Args:
            tag: Raw tag name encountered by the parser.

        Returns:
            ``None``. Sanitized output is appended internally.
        """
        lname = tag.lower()
        if lname in _DROP_WITH_CONTENT:
            if self._drop_depth:
                self._drop_depth -= 1
            return
        if self._drop_depth:
            return
        if not _is_allowed_tag(lname, self._profile) or lname in _VOID_TAGS:
            return
        self._parts.append(f"</{lname}>")
        if lname == "style" and self._style_depth:
            self._style_depth -= 1

    def handle_data(self, data: str) -> None:
        """Handle text or style content during sanitization.

        Args:
            data: Raw text data encountered by the parser.

        Returns:
            ``None``. Sanitized output is appended internally.
        """
        if self._drop_depth:
            return
        if self._style_depth:
            sanitized_css = _sanitize_css(data)
            if sanitized_css:
                self._parts.append(sanitized_css)
            return
        self._parts.append(data)

    def handle_entityref(self, name: str) -> None:
        """Preserve an entity reference when it is safe to emit.

        Args:
            name: Entity name without the surrounding ``&`` and ``;``.

        Returns:
            ``None``. The entity is appended to the sanitized output.
        """
        if not self._drop_depth:
            self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        """Preserve a numeric character reference when safe to emit.

        Args:
            name: Character reference payload without surrounding markup.

        Returns:
            ``None``. The character reference is appended to the output.
        """
        if not self._drop_depth:
            self._parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        """Ignore HTML comments so hidden payloads are not preserved.

        Args:
            data: Comment text encountered by the parser.

        Returns:
            ``None``. Comments are intentionally discarded.
        """
        # Drop comments to avoid hidden payloads.
        return


def _is_allowed_tag(tag: str, profile: str) -> bool:
    """Check whether a tag name is allowed for the active profile.

    Args:
        tag: Lowercase tag name to validate.
        profile: Sanitizer profile name, either ``html`` or ``svg``.

    Returns:
        ``True`` when the tag is allowed for the profile.
    """
    if profile == "svg":
        return tag in _SVG_ALLOWED_TAGS
    return tag in _HTML_ALLOWED_TAGS


def _sanitize_attrs(
    tag: str,
    attrs: list[tuple[str, str | None]],
    profile: str,
) -> list[tuple[str, str]]:
    """Filter and normalize attributes for a sanitized tag.

    Args:
        tag: Lowercase tag name receiving the attributes.
        attrs: Raw attribute name/value pairs from the parser.
        profile: Sanitizer profile name, either ``html`` or ``svg``.

    Returns:
        Cleaned attribute pairs safe to emit in output.
    """
    out: list[tuple[str, str]] = []
    for raw_name, raw_value in attrs:
        if not raw_name:
            continue
        name = _CONTROL_CHAR_RE.sub("", raw_name.strip().lower())
        if not name or name.startswith("on"):
            continue
        value = "" if raw_value is None else _CONTROL_CHAR_RE.sub("", str(raw_value))
        cleaned = _sanitize_attr_value(tag, name, value, profile)
        if cleaned is None:
            continue
        out.append((name, cleaned))

    if tag == "a":
        has_blank = False
        has_rel = False
        for name, value in out:
            if name == "target" and value.strip().lower() == "_blank":
                has_blank = True
            if name == "rel":
                has_rel = True
        if has_blank and not has_rel:
            out.append(("rel", "noopener noreferrer"))
    return out


def _sanitize_attr_value(tag: str, name: str, value: str, profile: str) -> str | None:
    """Sanitize one attribute value according to tag and profile rules.

    Args:
        tag: Lowercase tag name receiving the attribute.
        name: Lowercase attribute name.
        value: Raw attribute value string.
        profile: Sanitizer profile name, either ``html`` or ``svg``.

    Returns:
        A cleaned attribute value, or ``None`` when the attribute is unsafe.
    """
    if profile == "html":
        if not _is_allowed_html_attr(tag, name):
            return None
    elif not _is_allowed_svg_attr(name):
        return None

    if name in _URI_ATTRS:
        return _sanitize_uri(value, attr_name=name, tag=tag)
    if name == "style":
        css = _sanitize_css(value)
        return css if css else None
    if name == "target":
        target = value.strip().lower()
        if target in {"_blank", "_self", "_parent", "_top"}:
            return target
        return None
    return value


def _is_allowed_html_attr(tag: str, name: str) -> bool:
    """Check whether an HTML attribute is allowed for a specific tag.

    Args:
        tag: Lowercase HTML tag name.
        name: Lowercase attribute name.

    Returns:
        ``True`` when the attribute is allowed on the tag.
    """
    if name in _HTML_GLOBAL_ATTRS:
        return True
    if name.startswith("data-") or name.startswith("aria-"):
        return True
    return name in _HTML_TAG_ATTRS.get(tag, frozenset())


def _is_allowed_svg_attr(name: str) -> bool:
    """Check whether an SVG attribute name is syntactically allowed.

    Args:
        name: Lowercase attribute name to validate.

    Returns:
        ``True`` when the attribute name is safe to preserve.
    """
    if name.startswith("data-") or name.startswith("aria-"):
        return True
    # Keep SVG quality high by allowing standard non-event attribute names.
    return bool(re.fullmatch(r"[a-zA-Z_:][a-zA-Z0-9_.:-]*", name))


def _sanitize_uri(value: str, *, attr_name: str, tag: str) -> str | None:
    """Sanitize a URI-valued HTML or SVG attribute.

    Args:
        value: Raw URI string to validate.
        attr_name: Attribute name carrying the URI.
        tag: Lowercase tag name receiving the attribute.

    Returns:
        A safe URI string, or ``None`` when the URI is disallowed.
    """
    raw = value.strip()
    if not raw:
        return None
    lower = raw.lower()
    if _CONTROL_CHAR_RE.search(raw):
        return None
    if lower.startswith(("javascript:", "vbscript:", "data:text/html")):
        return None
    if raw.startswith(("#", "/", "./", "../")):
        return raw
    if lower.startswith("data:"):
        if attr_name in {"src", "xlink:href"} and lower.startswith(_ALLOWED_DATA_IMAGE_PREFIXES):
            return raw
        return None

    parsed = urlparse(raw)
    scheme = parsed.scheme.lower()
    if not scheme:
        return raw
    if scheme in {"http", "https"}:
        return raw
    if attr_name == "href" and tag == "a" and scheme in {"mailto", "tel"}:
        return raw
    return None


def _sanitize_css(css: str) -> str:
    """Remove dangerous constructs from inline CSS text.

    Args:
        css: Raw CSS declaration text.

    Returns:
        Sanitized CSS, or an empty string when unsafe.
    """
    text = _CONTROL_CHAR_RE.sub("", css)
    if not text:
        return ""
    if _CSS_DANGEROUS_RE.search(text):
        return ""
    text = _CSS_IMPORT_RE.sub("", text)

    def _rewrite_url(match: re.Match[str]) -> str:
        """Rewrite one CSS ``url(...)`` token with a sanitized value.

        Args:
            match: Regex match for the full CSS ``url(...)`` token.

        Returns:
            A rewritten safe ``url(...)`` token, or ``url()`` when unsafe.
        """
        inner = match.group(1).strip().strip("\"'")
        safe = _sanitize_css_uri(inner)
        return f"url({safe})" if safe else "url()"

    text = _CSS_URL_RE.sub(_rewrite_url, text)
    return text


def _sanitize_css_uri(value: str) -> str | None:
    """Allow only intra-document references or image data URIs in CSS.

    Args:
        value: Raw URI string extracted from CSS.

    Returns:
        A safe URI string, or ``None`` when the URI is disallowed.
    """
    raw = value.strip()
    if not raw or _CONTROL_CHAR_RE.search(raw):
        return None
    if raw.startswith("#"):
        return raw
    if raw.lower().startswith("data:"):
        return _sanitize_uri(raw, attr_name="src", tag="img")
    return None


def _start_tag(tag: str, attrs: list[tuple[str, str]]) -> str:
    """Render a sanitized opening tag string.

    Args:
        tag: Lowercase tag name to render.
        attrs: Sanitized attribute pairs for the tag.

    Returns:
        Opening tag HTML with escaped attribute values.
    """
    if not attrs:
        return f"<{tag}>"
    rendered = " ".join(f'{name}="{html.escape(value, quote=True)}"' for name, value in attrs)
    return f"<{tag} {rendered}>"


def _self_closing_tag(tag: str, attrs: list[tuple[str, str]]) -> str:
    """Render a sanitized self-closing tag string.

    Args:
        tag: Lowercase tag name to render.
        attrs: Sanitized attribute pairs for the tag.

    Returns:
        Self-closing tag HTML with escaped attribute values.
    """
    if not attrs:
        return f"<{tag}>"
    rendered = " ".join(f'{name}="{html.escape(value, quote=True)}"' for name, value in attrs)
    return f"<{tag} {rendered}>"
