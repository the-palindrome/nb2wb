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
    """Sanitize an HTML/SVG fragment using a parser-based allowlist."""
    parser = _FragmentSanitizer(profile=profile)
    parser.feed(fragment)
    parser.close()
    return parser.html


class _FragmentSanitizer(HTMLParser):
    """Streaming sanitizer for HTML fragments."""

    def __init__(self, *, profile: str) -> None:
        super().__init__(convert_charrefs=False)
        if profile not in {"html", "svg"}:
            raise ValueError(f"Unknown sanitizer profile: {profile}")
        self._profile = profile
        self._parts: list[str] = []
        self._drop_depth = 0
        self._style_depth = 0

    @property
    def html(self) -> str:
        return "".join(self._parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
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
        lname = tag.lower()
        if lname in _DROP_WITH_CONTENT or self._drop_depth:
            return
        if not _is_allowed_tag(lname, self._profile):
            return
        clean_attrs = _sanitize_attrs(lname, attrs, self._profile)
        self._parts.append(_self_closing_tag(lname, clean_attrs))

    def handle_endtag(self, tag: str) -> None:
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
        if self._drop_depth:
            return
        if self._style_depth:
            sanitized_css = _sanitize_css(data)
            if sanitized_css:
                self._parts.append(sanitized_css)
            return
        self._parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if not self._drop_depth:
            self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self._drop_depth:
            self._parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        # Drop comments to avoid hidden payloads.
        return


def _is_allowed_tag(tag: str, profile: str) -> bool:
    if profile == "svg":
        return tag in _SVG_ALLOWED_TAGS
    return tag in _HTML_ALLOWED_TAGS


def _sanitize_attrs(
    tag: str,
    attrs: list[tuple[str, str | None]],
    profile: str,
) -> list[tuple[str, str]]:
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
    if name in _HTML_GLOBAL_ATTRS:
        return True
    if name.startswith("data-") or name.startswith("aria-"):
        return True
    return name in _HTML_TAG_ATTRS.get(tag, frozenset())


def _is_allowed_svg_attr(name: str) -> bool:
    if name.startswith("data-") or name.startswith("aria-"):
        return True
    # Keep SVG quality high by allowing standard non-event attribute names.
    return bool(re.fullmatch(r"[a-zA-Z_:][a-zA-Z0-9_.:-]*", name))


def _sanitize_uri(value: str, *, attr_name: str, tag: str) -> str | None:
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
    text = _CONTROL_CHAR_RE.sub("", css)
    if not text:
        return ""
    if _CSS_DANGEROUS_RE.search(text):
        return ""
    text = _CSS_IMPORT_RE.sub("", text)

    def _rewrite_url(match: re.Match[str]) -> str:
        inner = match.group(1).strip().strip("\"'")
        safe = _sanitize_css_uri(inner)
        return f"url({safe})" if safe else "url()"

    text = _CSS_URL_RE.sub(_rewrite_url, text)
    return text


def _sanitize_css_uri(value: str) -> str | None:
    """Allow only intra-document references or image data URIs in CSS."""
    raw = value.strip()
    if not raw or _CONTROL_CHAR_RE.search(raw):
        return None
    if raw.startswith("#"):
        return raw
    if raw.lower().startswith("data:"):
        return _sanitize_uri(raw, attr_name="src", tag="img")
    return None


def _start_tag(tag: str, attrs: list[tuple[str, str]]) -> str:
    if not attrs:
        return f"<{tag}>"
    rendered = " ".join(f'{name}="{html.escape(value, quote=True)}"' for name, value in attrs)
    return f"<{tag} {rendered}>"


def _self_closing_tag(tag: str, attrs: list[tuple[str, str]]) -> str:
    if not attrs:
        return f"<{tag}>"
    rendered = " ".join(f'{name}="{html.escape(value, quote=True)}"' for name, value in attrs)
    return f"<{tag} {rendered}>"
