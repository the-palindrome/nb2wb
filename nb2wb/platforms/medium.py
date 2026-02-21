"""
Medium platform HTML builder.
"""
from __future__ import annotations

from ._templates import COPYABLE_SCRIPT, build_page
from .base import PlatformBuilder

_THEME = {
    "body-font-family": 'charter, Georgia, Cambria, "Times New Roman", Times, serif',
    "body-font-size": "20px",
    "body-line-height": "1.8",
    "body-color": "#242424",
    "body-max-width": "700px",
    "body-padding": "24px 20px 60px",
    "body-background": "#fff",
    "toolbar-background": "#1a8917",
    "toolbar-color": "#fff",
    "toolbar-shadow": "0 2px 8px rgba(0,0,0,0.15)",
    "toolbar-button-background": "#fff",
    "toolbar-button-color": "#1a8917",
    "toolbar-button-hover-background": "#e6f4e6",
    "toolbar-button-radius": "20px",
    "content-background": "#fff",
    "content-padding": "0",
    "content-radius": "0",
    "content-shadow": "none",
    "md-cell-margin": "1.4em",
    "code-cell-margin": "1.6em 0",
    "heading-font-family": 'sohne, "Helvetica Neue", Helvetica, Arial, sans-serif',
    "heading-font-weight": "700",
    "heading-color": "#242424",
    "heading-margin": "1.6em 0 0.4em",
    "h1-size": "2em",
    "h2-size": "1.6em",
    "h3-size": "1.3em",
    "h3-letter-spacing": "-0.02em",
    "blockquote-border": "#242424",
    "blockquote-color": "#242424",
    "mono-font-family": 'Menlo, Monaco, "Courier New", Courier, monospace',
    "mono-font-size": "0.85em",
    "pre-background": "#f2f2f2",
    "pre-padding": "1.2em",
    "inline-code-background": "#f2f2f2",
    "inline-code-padding": "0.15em 0.4em",
    "inline-code-radius": "3px",
    "table-border": "#e0e0e0",
    "table-header-background": "#f9f9f9",
    "hr-border": "#e0e0e0",
    "link-color": "inherit",
    "footer-border": "#e6e6e6",
    "footer-color": "#999",
    "copy-image-button-background": "rgba(26, 137, 23, 0.9)",
    "copy-image-button-hover-background": "rgba(13, 95, 11, 0.95)",
    "copy-image-button-copied-background": "#0d5f0b",
}


class MediumBuilder(PlatformBuilder):
    """HTML builder optimized for Medium."""

    @property
    def name(self) -> str:
        return "Medium"

    def build_page(self, content_html: str) -> str:
        """Wrap content in Medium-optimized HTML page."""
        content_html = self._make_images_copyable(content_html)
        return build_page(
            content_html,
            title="nb2wb — Medium Preview",
            toolbar_message="Paste into Medium. If images are missing, hover each one to copy it.",
            script=COPYABLE_SCRIPT,
            theme_overrides=_THEME,
        )
