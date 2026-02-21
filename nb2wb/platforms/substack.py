"""
Substack platform HTML builder.
"""
from __future__ import annotations

from ._templates import SIMPLE_COPY_SCRIPT, build_page
from .base import PlatformBuilder

_THEME = {
    "body-font-family": 'Georgia, "Times New Roman", serif',
    "body-font-size": "18px",
    "body-line-height": "1.7",
    "body-color": "#222",
    "body-max-width": "960px",
    "body-padding": "24px 16px 60px",
    "body-background": "#f0f0f0",
    "toolbar-background": "#1e1e2e",
    "toolbar-color": "#cdd6f4",
    "toolbar-shadow": "0 2px 8px rgba(0,0,0,0.25)",
    "toolbar-button-background": "#89b4fa",
    "toolbar-button-color": "#1e1e2e",
    "toolbar-button-hover-background": "#74c7ec",
    "toolbar-button-radius": "6px",
    "content-background": "#fff",
    "content-padding": "48px 56px",
    "content-radius": "8px",
    "content-shadow": "0 2px 12px rgba(0,0,0,0.08)",
    "md-cell-margin": "1.2em",
    "code-cell-margin": "1.4em 0",
    "heading-font-family": '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
    "heading-font-weight": "700",
    "heading-color": "currentColor",
    "heading-margin": "1.4em 0 0.5em",
    "h1-size": "2em",
    "h2-size": "1.5em",
    "h3-size": "1.17em",
    "h3-letter-spacing": "normal",
    "blockquote-border": "#ddd",
    "blockquote-color": "#666",
    "mono-font-family": '"DejaVu Sans Mono", "Fira Code", Consolas, monospace',
    "mono-font-size": "0.85em",
    "pre-background": "#f4f4f4",
    "pre-padding": "1em",
    "inline-code-background": "transparent",
    "inline-code-padding": "0",
    "inline-code-radius": "0",
    "table-border": "#ddd",
    "table-header-background": "#f4f4f4",
    "hr-border": "#ddd",
    "link-color": "inherit",
    "footer-border": "#eee",
    "footer-color": "#aaa",
}

_EXTRA_CSS = """\
    #toolbar p { opacity: 0.7; }
    ul, ol { padding-left: 1.6em; }
    li { margin-bottom: 0.25em; }
"""


class SubstackBuilder(PlatformBuilder):
    """HTML builder optimized for Substack."""

    @property
    def name(self) -> str:
        return "Substack"

    def build_page(self, content_html: str) -> str:
        """Wrap content in Substack-optimized HTML page."""
        content_html = self._embed_images_as_data_uris(content_html)
        return build_page(
            content_html,
            title="nb2wb — Substack Preview",
            toolbar_message="Then paste directly into your Substack draft.",
            script=SIMPLE_COPY_SCRIPT,
            theme_overrides=_THEME,
            extra_css=_EXTRA_CSS,
        )
