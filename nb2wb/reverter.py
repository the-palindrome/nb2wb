from __future__ import annotations

from dataclasses import dataclass
import html
import json
import logging
from pathlib import Path
import re
from typing import Callable, Iterable
from urllib.parse import quote, urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag
import nbformat

from ._reader_utils import make_notebook
from .ocr.base import OCRRequest
from .reverse_images import infer_supported_language_from_parts, normalize_supported_language

try:
    from markdownify import markdownify as _markdownify
except ImportError:  # pragma: no cover - exercised only when dependency is missing.
    _markdownify = None

_PROSE_TAGS = {
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "table",
    "blockquote",
    "hr",
    "dl",
}
_CONTAINER_TAGS = {
    "article",
    "body",
    "main",
    "section",
    "div",
    "aside",
    "header",
    "footer",
    "span",
}
_INLINE_IMAGE_WRAPPERS = {"p", "div", "a"}
_CODE_ATTR_KEYS = ("data-language", "data-lang", "language", "lang")
_LANG_CLASS_RE = re.compile(r"^(?:language|lang)-([a-z0-9+-]+)$", re.IGNORECASE)
_VIDEO_PLACEHOLDER_CLASS = "native-video-embed"
_VIDEO_PLACEHOLDER_COMPONENT = "VideoPlaceholder"
_VIDEO_MARKER_PREFIX = "NB2WBVIDEOBLOCK"
_MEDIA_UPLOAD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,255}$")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProseBlock:
    """Represent a prose HTML fragment extracted from a source document.

    Attributes:
        html: Raw HTML fragment preserved for later Markdown conversion.
    """

    html: str


@dataclass(frozen=True)
class CodeBlock:
    """Represent a source code block extracted from HTML.

    Attributes:
        source: Code text extracted from the block.
        language_label: Raw language hint found in HTML attributes or classes.
        language: Normalized notebook language name, if recognized.
    """

    source: str
    language_label: str | None
    language: str | None


@dataclass(frozen=True)
class ImageBlock:
    """Represent an image block and any OCR-derived classification data.

    Attributes:
        src: Image source URL, path, or data URI.
        alt: Image alt text from the source document.
        language: Inferred code language when the OCR result is code.
        ocr_result: Normalized OCR output mapping for the image.
    """

    src: str
    alt: str
    language: str | None
    ocr_result: dict[str, str]


Block = ProseBlock | CodeBlock | ImageBlock


class Reverter:
    """Convert HTML content into a scaffolded notebook."""

    def __init__(
        self,
        *,
        source_dir: Path | None = None,
        source_origin: str | None = None,
        ocr_pipeline: Callable[[OCRRequest], dict[str, str]] | None = None,
    ) -> None:
        """Configure HTML-to-notebook reversion helpers.

        Args:
            source_dir: Base directory for resolving relative image paths.
            source_origin: Canonical source origin used to rebuild media URLs.
            ocr_pipeline: Optional callable used to transcribe images.

        Returns:
            ``None``. The reverter stores the supplied helpers.
        """
        self._source_dir = source_dir
        self._source_origin = _normalize_source_origin(source_origin)
        self._ocr_pipeline = ocr_pipeline

    def revert_html(self, document: str) -> nbformat.NotebookNode:
        """Convert an HTML document into a scaffolded notebook payload.

        Args:
            document: Full HTML document or fragment to reverse-convert.

        Returns:
            A notebook scaffold containing markdown and code cells.
        """
        logger.debug("Reverter starting HTML parse")
        soup = BeautifulSoup(document, "html.parser")
        root = self._content_root(soup)
        source_origin = self._source_origin or _detect_source_origin(soup)
        blocks = self._extract_blocks(root)
        prose_count = sum(isinstance(block, ProseBlock) for block in blocks)
        code_count = sum(isinstance(block, CodeBlock) for block in blocks)
        image_count = sum(isinstance(block, ImageBlock) for block in blocks)
        logger.debug(
            "Extracted %d blocks (prose=%d, code=%d, images=%d)",
            len(blocks),
            prose_count,
            code_count,
            image_count,
        )
        notebook_language = self._select_notebook_language(blocks)
        cells = self._assemble_cells(blocks, source_origin=source_origin)
        notebook = make_notebook(cells, notebook_language)
        notebook.metadata["wb2nb"] = {"source_format": "html", "reverse_scaffold": 1}
        logger.debug(
            "Reverter finished (language=%s, cells=%d)",
            notebook_language,
            len(cells),
        )
        return notebook

    def _content_root(self, soup: BeautifulSoup) -> Tag:
        """Choose the most relevant content root from an HTML document.

        Args:
            soup: Parsed BeautifulSoup document tree.

        Returns:
            The tag that should be treated as the main content container.
        """
        for name in ("article", "main", "body"):
            match = soup.find(name)
            if isinstance(match, Tag):
                return match
        return soup

    def _extract_blocks(self, node: Tag) -> list[Block]:
        """Extract prose, code, and image blocks from a content container.

        Args:
            node: Root HTML tag whose children should be traversed.

        Returns:
            Ordered content blocks derived from the HTML structure.
        """
        blocks: list[Block] = []
        prose_fragments: list[str] = []

        def flush_prose() -> None:
            """Commit buffered prose HTML into a ``ProseBlock``.

            Args:
                None.

            Returns:
                ``None``. Buffered prose is appended to the block list.
            """
            if not prose_fragments:
                return
            html_fragment = "".join(prose_fragments).strip()
            prose_fragments.clear()
            if html_fragment:
                blocks.append(ProseBlock(html_fragment))

        for child in node.children:
            if isinstance(child, NavigableString):
                text = str(child)
                if text.strip():
                    prose_fragments.append(html.escape(text))
                continue
            if not isinstance(child, Tag):
                continue
            if _is_video_placeholder_tag(child):
                prose_fragments.append(str(child))
                continue
            if self._is_code_block(child):
                flush_prose()
                blocks.append(self._make_code_block(child))
                continue
            if self._is_image_block(child):
                flush_prose()
                blocks.append(self._make_image_block(child))
                continue
            if child.name in _PROSE_TAGS:
                prose_fragments.append(str(child))
                continue
            if child.name in _CONTAINER_TAGS:
                flush_prose()
                nested = self._extract_blocks(child)
                if nested:
                    blocks.extend(nested)
                else:
                    text = child.get_text(" ", strip=True)
                    if text:
                        blocks.append(ProseBlock(html.escape(text)))
                continue
            prose_fragments.append(str(child))

        flush_prose()
        return self._merge_adjacent_prose(blocks)

    def _select_notebook_language(self, blocks: Iterable[Block]) -> str:
        """Pick a default notebook language from extracted code blocks.

        Args:
            blocks: Ordered content blocks extracted from the document.

        Returns:
            The first recognized code language, or ``python`` by default.
        """
        for block in blocks:
            if isinstance(block, CodeBlock) and block.language is not None:
                return block.language
        return "python"

    def _assemble_cells(
        self,
        blocks: list[Block],
        *,
        source_origin: str | None = None,
    ) -> list[nbformat.NotebookNode]:
        """Convert extracted blocks into notebook cells.

        Args:
            blocks: Ordered prose, code, and image blocks.
            source_origin: Canonical source origin for rebuilding media URLs.

        Returns:
            A list of notebook cells suitable for notebook assembly.
        """
        cells: list[nbformat.NotebookNode] = []
        pending_markdown: list[str] = []

        def flush_markdown() -> None:
            """Commit buffered markdown fragments into one notebook cell.

            Args:
                None.

            Returns:
                ``None``. Buffered markdown is appended to the cell list.
            """
            if not pending_markdown:
                return
            joined = "\n\n".join(part for part in pending_markdown if part.strip()).strip()
            pending_markdown.clear()
            if joined:
                cells.append(nbformat.v4.new_markdown_cell(joined))

        for block in blocks:
            if isinstance(block, ProseBlock):
                markdown_text = _html_to_markdown(
                    block.html,
                    source_origin=source_origin,
                ).strip()
                if markdown_text:
                    pending_markdown.append(markdown_text)
                continue

            if isinstance(block, CodeBlock):
                flush_markdown()
                if block.language is not None:
                    cell = nbformat.v4.new_code_cell(block.source)
                    cell.metadata["language"] = block.language
                    cells.append(cell)
                else:
                    language_suffix = block.language_label or ""
                    cells.append(
                        nbformat.v4.new_markdown_cell(
                            _fenced_code_block(block.source, language_suffix)
                        )
                    )
                continue

            ocr_result = block.ocr_result
            if ocr_result["type"] == "figure":
                pending_markdown.append(_markdown_image(block.src, block.alt))
                continue

            flush_markdown()
            metadata = {
                "source_kind": "image",
                "classification": ocr_result["type"],
                "src": block.src,
                "alt": block.alt,
            }
            metadata["ocr_type"] = ocr_result["type"]
            cell = _ocr_result_to_cell(
                ocr_result,
                language=block.language,
            )
            assert cell is not None
            cell.metadata["wb2nb"] = metadata
            cells.append(cell)

        flush_markdown()
        return cells

    def _is_code_block(self, tag: Tag) -> bool:
        """Check whether an HTML tag should be treated as a code block.

        Args:
            tag: Candidate HTML tag from the parsed document.

        Returns:
            ``True`` when the tag contains extractable preformatted code.
        """
        return tag.name == "pre" and bool(_extract_code_source(tag))

    def _is_image_block(self, tag: Tag) -> bool:
        """Check whether an HTML tag should be treated as an image block.

        Args:
            tag: Candidate HTML tag from the parsed document.

        Returns:
            ``True`` when the tag represents a standalone image block.
        """
        if tag.name == "img":
            return True
        if tag.name in {"figure", "picture"} and tag.find("img"):
            return True
        if tag.name not in _INLINE_IMAGE_WRAPPERS:
            return False
        if not tag.find("img"):
            return False

        text_nodes = [text.strip() for text in tag.find_all(string=True) if text.strip()]
        visible_text = " ".join(
            text
            for text in text_nodes
            if text != (tag.find("figcaption").get_text(" ", strip=True) if tag.find("figcaption") else "")
        ).strip()
        return not visible_text

    def _make_code_block(self, tag: Tag) -> CodeBlock:
        """Build a ``CodeBlock`` from a preformatted HTML node.

        Args:
            tag: HTML tag containing source code content.

        Returns:
            A normalized ``CodeBlock`` instance.
        """
        source = _extract_code_source(tag)
        raw_language = _detect_code_language(tag)
        return CodeBlock(
            source=source,
            language_label=raw_language,
            language=normalize_supported_language(raw_language),
        )

    def _make_image_block(self, tag: Tag) -> ImageBlock:
        """Build an ``ImageBlock`` from an image-containing HTML node.

        Args:
            tag: HTML tag containing an image element.

        Returns:
            A normalized ``ImageBlock`` with optional OCR metadata.
        """
        img = tag if tag.name == "img" else tag.find("img")
        assert isinstance(img, Tag)
        img_classes = tuple(_collect_classes(img))
        request = OCRRequest(
            src=img.get("src", ""),
            alt=img.get("alt", ""),
            title=img.get("title", ""),
            classes=tuple(dict.fromkeys([*_collect_classes(tag), *img_classes])),
            caption=_caption_text(tag),
            nearby_text=_nearby_text(tag),
            source_dir=self._source_dir,
        )
        if self._ocr_pipeline is None:
            logger.debug(
                "OCR disabled for image source=%s",
                _summarize_debug_text(request.src),
            )
            ocr_result = {"type": "figure", "payload": ""}
        else:
            logger.debug(
                "Running OCR for image source=%s",
                _summarize_debug_text(request.src),
            )
            ocr_result = _normalize_ocr_result(self._ocr_pipeline(request))
            logger.debug(
                "OCR classified image source=%s as %s",
                _summarize_debug_text(request.src),
                ocr_result["type"],
            )
        return ImageBlock(
            src=request.src,
            alt=request.alt,
            language=_infer_image_language(request, ocr_result),
            ocr_result=ocr_result,
        )

    def _merge_adjacent_prose(self, blocks: list[Block]) -> list[Block]:
        """Merge neighboring prose fragments into larger prose blocks.

        Args:
            blocks: Ordered content blocks extracted from the document.

        Returns:
            A new block list with adjacent prose blocks coalesced.
        """
        merged: list[Block] = []
        for block in blocks:
            if merged and isinstance(block, ProseBlock) and isinstance(merged[-1], ProseBlock):
                merged[-1] = ProseBlock(f"{merged[-1].html}\n{block.html}")
            else:
                merged.append(block)
        return merged


def _extract_code_source(tag: Tag) -> str:
    """Extract source text from a ``pre`` or nested ``code`` tag.

    Args:
        tag: HTML tag containing code markup.

    Returns:
        Stripped source code text.
    """
    code = tag.find("code")
    source = code.get_text("\n", strip=False) if isinstance(code, Tag) else tag.get_text("\n", strip=False)
    return source.strip("\n")


def _detect_code_language(tag: Tag) -> str | None:
    """Find the first language hint associated with a code block.

    Args:
        tag: HTML tag containing code markup.

    Returns:
        A normalized raw language label, or ``None`` when unavailable.
    """
    for candidate in _language_candidates(tag):
        normalized = candidate.strip().lower()
        if normalized:
            return normalized
    return None


def _language_candidates(tag: Tag) -> Iterable[str]:
    """Yield raw language hints from code block attributes and classes.

    Args:
        tag: HTML tag containing code markup.

    Returns:
        An iterator of candidate language strings.
    """
    nodes: list[Tag] = [tag]
    code = tag.find("code")
    if isinstance(code, Tag):
        nodes.append(code)
    parent = tag.parent
    if isinstance(parent, Tag):
        nodes.append(parent)

    for node in nodes:
        for key in _CODE_ATTR_KEYS:
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                yield value
        for cls in _collect_classes(node):
            match = _LANG_CLASS_RE.match(cls)
            if match:
                yield match.group(1)


def _collect_classes(tag: Tag) -> list[str]:
    """Return a normalized list of CSS classes from an HTML tag.

    Args:
        tag: HTML tag whose ``class`` attribute should be read.

    Returns:
        A list of class names as strings.
    """
    classes = tag.get("class", [])
    if isinstance(classes, str):
        return [classes]
    return [str(cls) for cls in classes]


def _is_video_placeholder_tag(tag: Tag) -> bool:
    """Return ``True`` when a node matches a native video placeholder."""
    component_name = tag.get("data-component-name")
    if isinstance(component_name, str) and component_name.strip() == _VIDEO_PLACEHOLDER_COMPONENT:
        return True
    classes = tag.get("class", [])
    if isinstance(classes, str):
        class_tokens = [token for token in classes.split() if token]
    else:
        class_tokens = []
        for cls in classes:
            class_tokens.extend(token for token in str(cls).split() if token)
    return any(token.lower() == _VIDEO_PLACEHOLDER_CLASS for token in class_tokens)


def _summarize_debug_text(value: str, *, limit: int = 120) -> str:
    """Trim debug strings so log lines stay readable."""
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def _caption_text(tag: Tag) -> str:
    """Extract figure caption text from an image wrapper tag.

    Args:
        tag: HTML tag that may contain a ``figcaption`` element.

    Returns:
        Caption text, or an empty string when none is present.
    """
    caption = tag.find("figcaption")
    if isinstance(caption, Tag):
        return caption.get_text(" ", strip=True)
    return ""


def _nearby_text(tag: Tag) -> str:
    """Collect nearby visible text that may describe an image.

    Args:
        tag: HTML tag associated with an image block.

    Returns:
        Deduplicated text from the tag and its parent container.
    """
    parts: list[str] = []
    for node in (tag, tag.parent if isinstance(tag.parent, Tag) else None):
        if not isinstance(node, Tag):
            continue
        text = node.get_text(" ", strip=True)
        if text:
            parts.append(text)
    return " ".join(dict.fromkeys(parts))


def _infer_image_language(request: OCRRequest, ocr_result: dict[str, str]) -> str | None:
    """Infer a code language for OCR-derived code images.

    Args:
        request: OCR request describing the image and nearby context.
        ocr_result: Normalized OCR result mapping for the image.

    Returns:
        A supported language name, or ``None`` when no hint is found.
    """
    if ocr_result["type"] != "code":
        return None
    return infer_supported_language_from_parts(
        (
            request.alt,
            request.title,
            request.caption,
            request.nearby_text,
            " ".join(request.classes),
            request.src,
        )
    )


def _fenced_code_block(source: str, language: str) -> str:
    """Render source text as a fenced Markdown code block.

    Args:
        source: Code text to wrap in Markdown fences.
        language: Raw language suffix to append to the opening fence.

    Returns:
        A fenced Markdown code block string.
    """
    fence = "```"
    language_suffix = language.strip()
    header = f"{fence}{language_suffix}".rstrip()
    return f"{header}\n{source.rstrip()}\n{fence}"


def _markdown_image(src: str, alt: str) -> str:
    """Render a Markdown image reference.

    Args:
        src: Image source URL or path.
        alt: Alt text for the image.

    Returns:
        Markdown image syntax for the provided values.
    """
    return f"![{alt}]({src})"


def _latex_markdown(latex: str) -> str:
    """Wrap LaTeX text as a display-math Markdown block.

    Args:
        latex: LaTeX expression to normalize.

    Returns:
        Display-math Markdown containing the expression.
    """
    stripped = latex.strip()
    if stripped.startswith("$$") and stripped.endswith("$$"):
        return stripped
    return f"$$\n{stripped}\n$$"


def _html_to_markdown(
    fragment: str,
    *,
    source_origin: str | None = None,
) -> str:
    """Convert HTML into Markdown using the best available backend.

    Args:
        fragment: HTML fragment to convert.
        source_origin: Canonical source origin used to rebuild media links.

    Returns:
        Markdown text derived from the fragment.
    """
    fragment_to_convert = fragment
    video_replacements: dict[str, str] = {}
    if _contains_video_markup(fragment):
        fragment_to_convert, video_replacements = _prepare_video_fragments(
            fragment,
            source_origin=source_origin,
        )

    if _markdownify is not None:
        markdown = _markdownify(fragment_to_convert, heading_style="ATX").strip()
    else:
        markdown = _fallback_html_to_markdown(fragment_to_convert).strip()

    return _restore_video_markers(markdown, video_replacements).strip()


def _contains_video_markup(fragment: str) -> bool:
    """Check whether an HTML fragment may contain video content."""
    lowered = fragment.lower()
    return (
        "<video" in lowered
        or "<source" in lowered
        or _VIDEO_PLACEHOLDER_CLASS in lowered
        or _VIDEO_PLACEHOLDER_COMPONENT.lower() in lowered
    )


def _prepare_video_fragments(
    fragment: str,
    *,
    source_origin: str | None,
) -> tuple[str, dict[str, str]]:
    """Replace video-related nodes with markers before Markdown conversion."""
    soup = BeautifulSoup(fragment, "html.parser")
    replacements: dict[str, str] = {}
    marker_index = 0

    for placeholder in [tag for tag in soup.find_all(True) if _is_video_placeholder_tag(tag)]:
        replacement = _video_placeholder_markdown(
            placeholder,
            source_origin=source_origin,
        )
        if not replacement:
            placeholder.decompose()
            continue
        marker = f"{_VIDEO_MARKER_PREFIX}{marker_index}"
        marker_index += 1
        replacements[marker] = replacement
        placeholder.replace_with(NavigableString(marker))

    for video in soup.find_all("video"):
        marker = f"{_VIDEO_MARKER_PREFIX}{marker_index}"
        marker_index += 1
        replacements[marker] = str(video)
        video.replace_with(NavigableString(marker))

    for source in soup.find_all("source"):
        if source.find_parent("video") is not None:
            continue
        marker = f"{_VIDEO_MARKER_PREFIX}{marker_index}"
        marker_index += 1
        replacements[marker] = str(source)
        source.replace_with(NavigableString(marker))

    return str(soup), replacements


def _restore_video_markers(markdown: str, replacements: dict[str, str]) -> str:
    """Restore captured video snippets after Markdown conversion."""
    if not replacements:
        return markdown
    rendered = markdown
    for marker, replacement in replacements.items():
        rendered = rendered.replace(marker, replacement)
    return rendered


def _video_placeholder_markdown(
    tag: Tag,
    *,
    source_origin: str | None,
) -> str:
    """Render a native video placeholder node into Markdown-safe output."""
    media_upload_id = _extract_media_upload_id_from_placeholder(tag)
    if media_upload_id is None:
        return ""

    if not source_origin:
        return f"Video upload ID: `{media_upload_id}`"

    video_url = _video_mp4_url(source_origin, media_upload_id)
    escaped_video_url = html.escape(video_url, quote=True)
    return (
        f'<video controls preload="metadata" playsinline src="{escaped_video_url}"></video>\n\n'
        f"[Open video]({video_url})"
    )


def _extract_media_upload_id_from_placeholder(tag: Tag) -> str | None:
    """Decode and parse placeholder attrs to extract ``mediaUploadId``."""
    raw_data_attrs = tag.get("data-attrs")
    if not isinstance(raw_data_attrs, str):
        return None

    attrs = _decode_data_attrs(raw_data_attrs)
    if attrs is None:
        return None

    media_upload_id = attrs.get("mediaUploadId")
    if not isinstance(media_upload_id, str):
        return None
    media_upload_id = media_upload_id.strip()
    if not media_upload_id or not _is_valid_media_upload_id(media_upload_id):
        return None
    return media_upload_id


def _decode_data_attrs(raw_data_attrs: str) -> dict[str, object] | None:
    """Decode HTML-escaped placeholder attrs and parse them as JSON."""
    decoded = html.unescape(raw_data_attrs).strip()
    if not decoded:
        return None
    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _is_valid_media_upload_id(media_upload_id: str) -> bool:
    """Return ``True`` when a media upload id is shape-valid."""
    return bool(_MEDIA_UPLOAD_ID_RE.fullmatch(media_upload_id))


def _video_mp4_url(source_origin: str, media_upload_id: str) -> str:
    """Build a direct MP4 URL for a media upload id."""
    encoded_id = quote(media_upload_id, safe="")
    return f"{source_origin}/api/v1/video/upload/{encoded_id}/src?type=mp4"


def _normalize_source_origin(source_origin: str | None) -> str | None:
    """Normalize an origin value to ``<scheme>://<host[:port]>``."""
    if not isinstance(source_origin, str):
        return None
    candidate = source_origin.strip()
    if not candidate:
        return None
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _detect_source_origin(soup: BeautifulSoup) -> str | None:
    """Try to infer a canonical source origin from document metadata."""
    candidates: list[str] = []

    canonical_links = soup.find_all("link")
    for link in canonical_links:
        rel = link.get("rel", [])
        rel_tokens: list[str]
        if isinstance(rel, str):
            rel_tokens = [token for token in rel.split() if token]
        else:
            rel_tokens = [str(token) for token in rel]
        if not any(token.lower() == "canonical" for token in rel_tokens):
            continue
        href = link.get("href")
        if isinstance(href, str):
            candidates.append(href)

    for meta in soup.find_all("meta"):
        property_name = meta.get("property")
        name = meta.get("name")
        if property_name not in {"og:url"} and name not in {"twitter:url"}:
            continue
        content = meta.get("content")
        if isinstance(content, str):
            candidates.append(content)

    for candidate in candidates:
        normalized = _normalize_source_origin(candidate)
        if normalized is not None:
            return normalized
    return None


def _fallback_html_to_markdown(fragment: str) -> str:
    """Convert HTML to Markdown with the built-in fallback renderer.

    Args:
        fragment: HTML fragment to convert.

    Returns:
        Markdown text derived from the fragment.
    """
    soup = BeautifulSoup(fragment, "html.parser")
    return _render_children(soup).strip()


def _render_children(node: Tag | BeautifulSoup) -> str:
    """Render all child nodes of an HTML container to Markdown.

    Args:
        node: HTML tag or document fragment whose children should be rendered.

    Returns:
        Markdown string assembled from the child nodes.
    """
    parts: list[str] = []
    for child in node.children:
        rendered = _render_node(child)
        if rendered:
            parts.append(rendered)
    return _collapse_markdown(parts)


def _render_node(node: object) -> str:
    """Render one HTML node into Markdown text.

    Args:
        node: BeautifulSoup node to render.

    Returns:
        Markdown text for the node, or an empty string when unsupported.
    """
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""

    name = node.name.lower()
    if name in {"strong", "b"}:
        return f"**{_render_children(node).strip()}**"
    if name in {"em", "i"}:
        return f"*{_render_children(node).strip()}*"
    if name == "code":
        return f"`{node.get_text(strip=True)}`"
    if name == "a":
        text = _render_children(node).strip() or node.get("href", "")
        href = node.get("href", "")
        return f"[{text}]({href})" if href else text
    if name == "img":
        return _markdown_image(node.get("src", ""), node.get("alt", ""))
    if name == "p":
        return f"{_render_children(node).strip()}\n\n"
    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        level = int(name[1])
        return f"{'#' * level} {_render_children(node).strip()}\n\n"
    if name == "blockquote":
        text = _render_children(node).strip()
        lines = [f"> {line}" if line else ">" for line in text.splitlines()]
        return "\n".join(lines) + "\n\n"
    if name == "ul":
        return "".join(f"- {_render_children(item).strip()}\n" for item in node.find_all("li", recursive=False)) + "\n"
    if name == "ol":
        return "".join(
            f"{idx}. {_render_children(item).strip()}\n"
            for idx, item in enumerate(node.find_all("li", recursive=False), start=1)
        ) + "\n"
    if name == "br":
        return "\n"
    if name == "hr":
        return "---\n\n"
    return _render_children(node)


def _collapse_markdown(parts: list[str]) -> str:
    """Join Markdown fragments and collapse excessive blank lines.

    Args:
        parts: Markdown fragments collected during rendering.

    Returns:
        One normalized Markdown string.
    """
    text = "".join(parts)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_ocr_result(result: object) -> dict[str, str]:
    """Validate that an OCR pipeline returned the expected result shape.

    Args:
        result: Arbitrary object returned by the OCR pipeline.

    Returns:
        A normalized ``{"type", "payload"}`` result mapping.
    """
    if not isinstance(result, dict):
        raise TypeError("ocr_pipeline must return a dict with 'type' and 'payload'.")

    result_type = result.get("type")
    payload = result.get("payload")
    allowed_types = {"latex", "code", "table", "figure"}
    if result_type not in allowed_types:
        allowed = ", ".join(sorted(allowed_types))
        raise ValueError(f"ocr_pipeline result 'type' must be one of: {allowed}")
    if not isinstance(payload, str):
        raise TypeError("ocr_pipeline result 'payload' must be a string.")
    if result_type == "figure" and payload != "":
        raise ValueError("ocr_pipeline result 'figure' must use an empty payload.")

    return {"type": result_type, "payload": payload}


def _ocr_result_to_cell(
    result: dict[str, str],
    *,
    language: str | None,
) -> nbformat.NotebookNode | None:
    """Convert a normalized OCR result into a notebook cell.

    Args:
        result: Normalized OCR result mapping.
        language: Optional language metadata for code cells.

    Returns:
        A notebook cell, or ``None`` for figure-only image results.
    """
    result_type = result["type"]
    payload = result["payload"]

    if result_type == "figure":
        return None
    if result_type == "latex":
        return nbformat.v4.new_markdown_cell(_latex_markdown(payload))
    if result_type == "table":
        return nbformat.v4.new_markdown_cell(payload)

    cell = nbformat.v4.new_code_cell(payload)
    if language is not None:
        cell.metadata["language"] = language
    return cell
