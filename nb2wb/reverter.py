from __future__ import annotations

from dataclasses import dataclass
import html
from pathlib import Path
import re
from typing import Iterable

from bs4 import BeautifulSoup, NavigableString, Tag
import nbformat

from ._reader_utils import make_notebook
from .reverse_images import (
    DefaultImageClassifier,
    ImageCandidate,
    ImageClassification,
    extract_latex,
    infer_supported_language,
    normalize_supported_language,
)

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


@dataclass(frozen=True)
class ProseBlock:
    html: str


@dataclass(frozen=True)
class CodeBlock:
    source: str
    language_label: str | None
    language: str | None


@dataclass(frozen=True)
class ImageBlock:
    src: str
    alt: str
    classification: ImageClassification
    language: str | None
    ocr_text: str | None = None
    ocr_error: str | None = None


Block = ProseBlock | CodeBlock | ImageBlock


class Reverter:
    """Convert HTML content into a scaffolded notebook."""

    def __init__(
        self,
        *,
        source_dir: Path | None = None,
        ocr_device: str | None = None,
    ) -> None:
        self._classifier = DefaultImageClassifier()
        self._source_dir = source_dir
        self._ocr_device = ocr_device

    def revert_html(self, document: str) -> nbformat.NotebookNode:
        soup = BeautifulSoup(document, "html.parser")
        root = self._content_root(soup)
        blocks = self._extract_blocks(root)
        notebook_language = self._select_notebook_language(blocks)
        cells = self._assemble_cells(blocks)
        notebook = make_notebook(cells, notebook_language)
        notebook.metadata["wb2nb"] = {"source_format": "html", "reverse_scaffold": 1}
        return notebook

    def _content_root(self, soup: BeautifulSoup) -> Tag:
        for name in ("article", "main", "body"):
            match = soup.find(name)
            if isinstance(match, Tag):
                return match
        return soup

    def _extract_blocks(self, node: Tag) -> list[Block]:
        blocks: list[Block] = []
        prose_fragments: list[str] = []

        def flush_prose() -> None:
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
        for block in blocks:
            if isinstance(block, CodeBlock) and block.language is not None:
                return block.language
        return "python"

    def _assemble_cells(self, blocks: list[Block]) -> list[nbformat.NotebookNode]:
        cells: list[nbformat.NotebookNode] = []
        pending_markdown: list[str] = []

        def flush_markdown() -> None:
            if not pending_markdown:
                return
            joined = "\n\n".join(part for part in pending_markdown if part.strip()).strip()
            pending_markdown.clear()
            if joined:
                cells.append(nbformat.v4.new_markdown_cell(joined))

        for block in blocks:
            if isinstance(block, ProseBlock):
                markdown_text = _html_to_markdown(block.html).strip()
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

            if block.classification == "other":
                pending_markdown.append(_markdown_image(block.src, block.alt))
                continue

            flush_markdown()
            metadata = {
                "source_kind": "image",
                "classification": block.classification,
                "src": block.src,
                "alt": block.alt,
                "ocr_status": "pending",
            }
            if block.classification == "latex":
                if block.ocr_text is not None:
                    cell = nbformat.v4.new_markdown_cell(_latex_markdown(block.ocr_text))
                    metadata["ocr_status"] = "complete"
                    metadata["ocr_engine"] = "pix2text"
                else:
                    cell = nbformat.v4.new_markdown_cell(
                        _latex_placeholder(block.src, block.alt)
                    )
                    metadata["ocr_status"] = "failed"
                    if block.ocr_error is not None:
                        metadata["ocr_error"] = block.ocr_error
                cell.metadata["wb2nb"] = metadata
                cells.append(cell)
                continue
            if block.classification == "table":
                cell = nbformat.v4.new_markdown_cell(
                    _table_placeholder(block.src, block.alt)
                )
                cell.metadata["wb2nb"] = metadata
                cells.append(cell)
                continue
            if block.language is not None:
                cell = nbformat.v4.new_code_cell(_code_placeholder(block.src, block.alt))
                cell.metadata["language"] = block.language
                cell.metadata["wb2nb"] = metadata
                cells.append(cell)
                continue
            cell = nbformat.v4.new_markdown_cell(
                _fenced_code_block(
                    _unsupported_code_placeholder(block.src, block.alt),
                    "",
                )
            )
            cell.metadata["wb2nb"] = metadata
            cells.append(cell)

        flush_markdown()
        return cells

    def _is_code_block(self, tag: Tag) -> bool:
        return tag.name == "pre" and bool(_extract_code_source(tag))

    def _is_image_block(self, tag: Tag) -> bool:
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
        source = _extract_code_source(tag)
        raw_language = _detect_code_language(tag)
        return CodeBlock(
            source=source,
            language_label=raw_language,
            language=normalize_supported_language(raw_language),
        )

    def _make_image_block(self, tag: Tag) -> ImageBlock:
        img = tag if tag.name == "img" else tag.find("img")
        assert isinstance(img, Tag)
        img_classes = tuple(_collect_classes(img))
        candidate = ImageCandidate(
            src=img.get("src", ""),
            alt=img.get("alt", ""),
            title=img.get("title", ""),
            classes=tuple(dict.fromkeys([*_collect_classes(tag), *img_classes])),
            caption=_caption_text(tag),
            nearby_text=_nearby_text(tag),
            source_dir=self._source_dir,
        )
        classification = self._classifier.classify(candidate)
        ocr_text: str | None = None
        ocr_error: str | None = None
        if classification == "latex":
            try:
                ocr_text = extract_latex(candidate, device=self._ocr_device)
            except Exception as exc:
                ocr_error = str(exc)
        return ImageBlock(
            src=candidate.src,
            alt=candidate.alt,
            classification=classification,
            language=infer_supported_language(candidate) if classification == "code" else None,
            ocr_text=ocr_text,
            ocr_error=ocr_error,
        )

    def _merge_adjacent_prose(self, blocks: list[Block]) -> list[Block]:
        merged: list[Block] = []
        for block in blocks:
            if merged and isinstance(block, ProseBlock) and isinstance(merged[-1], ProseBlock):
                merged[-1] = ProseBlock(f"{merged[-1].html}\n{block.html}")
            else:
                merged.append(block)
        return merged


def _extract_code_source(tag: Tag) -> str:
    code = tag.find("code")
    source = code.get_text("\n", strip=False) if isinstance(code, Tag) else tag.get_text("\n", strip=False)
    return source.strip("\n")


def _detect_code_language(tag: Tag) -> str | None:
    for candidate in _language_candidates(tag):
        normalized = candidate.strip().lower()
        if normalized:
            return normalized
    return None


def _language_candidates(tag: Tag) -> Iterable[str]:
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
    classes = tag.get("class", [])
    if isinstance(classes, str):
        return [classes]
    return [str(cls) for cls in classes]


def _caption_text(tag: Tag) -> str:
    caption = tag.find("figcaption")
    if isinstance(caption, Tag):
        return caption.get_text(" ", strip=True)
    return ""


def _nearby_text(tag: Tag) -> str:
    parts: list[str] = []
    for node in (tag, tag.parent if isinstance(tag.parent, Tag) else None):
        if not isinstance(node, Tag):
            continue
        text = node.get_text(" ", strip=True)
        if text:
            parts.append(text)
    return " ".join(dict.fromkeys(parts))


def _fenced_code_block(source: str, language: str) -> str:
    fence = "```"
    language_suffix = language.strip()
    header = f"{fence}{language_suffix}".rstrip()
    return f"{header}\n{source.rstrip()}\n{fence}"


def _markdown_image(src: str, alt: str) -> str:
    return f"![{alt}]({src})"


def _latex_placeholder(src: str, alt: str) -> str:
    description = f" (alt: {alt})" if alt else ""
    return (
        "TODO(wb2nb): Replace this placeholder with OCR-extracted LaTeX.\n\n"
        f"Source image: `{src}`{description}"
    )


def _latex_markdown(latex: str) -> str:
    stripped = latex.strip()
    if stripped.startswith("$$") and stripped.endswith("$$"):
        return stripped
    return f"$$\n{stripped}\n$$"


def _code_placeholder(src: str, alt: str) -> str:
    description = f" | alt: {alt}" if alt else ""
    return (
        "# TODO(wb2nb): Replace this placeholder with OCR-extracted code.\n"
        f"# source_image: {src}{description}"
    )


def _unsupported_code_placeholder(src: str, alt: str) -> str:
    description = f" (alt: {alt})" if alt else ""
    return (
        "TODO(wb2nb): Replace this placeholder with OCR-extracted code from an "
        f"unsupported or unknown language image.\n\nSource image: {src}{description}"
    )


def _table_placeholder(src: str, alt: str) -> str:
    description = f" (alt: {alt})" if alt else ""
    return (
        "TODO(wb2nb): Replace this placeholder with OCR-extracted table content.\n\n"
        f"Source image: `{src}`{description}"
    )


def _html_to_markdown(fragment: str) -> str:
    if _markdownify is not None:
        return _markdownify(fragment, heading_style="ATX").strip()
    return _fallback_html_to_markdown(fragment).strip()


def _fallback_html_to_markdown(fragment: str) -> str:
    soup = BeautifulSoup(fragment, "html.parser")
    return _render_children(soup).strip()


def _render_children(node: Tag | BeautifulSoup) -> str:
    parts: list[str] = []
    for child in node.children:
        rendered = _render_node(child)
        if rendered:
            parts.append(rendered)
    return _collapse_markdown(parts)


def _render_node(node: object) -> str:
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
    text = "".join(parts)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
