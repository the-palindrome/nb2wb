"""
X (Twitter) Articles platform HTML builder.
"""
from __future__ import annotations

from ._templates import COPYABLE_SCRIPT, build_page
from .base import PlatformBuilder

_THEME = {
    "body-font-family": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    "body-font-size": "19px",
    "body-line-height": "1.6",
    "body-color": "#0f1419",
    "body-max-width": "680px",
    "body-padding": "24px 20px 60px",
    "body-background": "#fff",
    "toolbar-background": "#1d9bf0",
    "toolbar-color": "#fff",
    "toolbar-shadow": "0 2px 8px rgba(0,0,0,0.15)",
    "toolbar-button-background": "#fff",
    "toolbar-button-color": "#1d9bf0",
    "toolbar-button-hover-background": "#e8f5fe",
    "toolbar-button-radius": "20px",
    "content-background": "#fff",
    "content-padding": "0",
    "content-radius": "0",
    "content-shadow": "none",
    "md-cell-margin": "1.3em",
    "code-cell-margin": "1.5em 0",
    "heading-font-family": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    "heading-font-weight": "800",
    "heading-color": "#0f1419",
    "heading-margin": "1.5em 0 0.6em",
    "h1-size": "2.2em",
    "h2-size": "1.8em",
    "h3-size": "1.4em",
    "h3-letter-spacing": "normal",
    "blockquote-border": "#0f1419",
    "blockquote-color": "#0f1419",
    "mono-font-family": '"SF Mono", "Monaco", "Inconsolata", "Fira Code", monospace',
    "mono-font-size": "0.88em",
    "pre-background": "#f7f9f9",
    "pre-padding": "1.2em",
    "inline-code-background": "#f7f9f9",
    "inline-code-padding": "0.15em 0.4em",
    "inline-code-radius": "3px",
    "table-border": "#eff3f4",
    "table-header-background": "#f7f9f9",
    "hr-border": "#eff3f4",
    "link-color": "inherit",
    "footer-border": "#eff3f4",
    "footer-color": "#536471",
    "copy-image-button-background": "rgba(29, 155, 240, 0.9)",
    "copy-image-button-hover-background": "rgba(20, 120, 190, 0.95)",
    "copy-image-button-copied-background": "#1478be",
}


class XArticlesBuilder(PlatformBuilder):
    """HTML builder optimized for X (Twitter) Articles."""

    @property
    def name(self) -> str:
        return "X Articles"

    def build_page(self, content_html: str) -> str:
        """Wrap content in X Articles-optimized HTML page."""
        content_html = self._make_images_copyable(content_html)
        return build_page(
            content_html,
            title="nb2wb — X Articles Preview",
            toolbar_message="Paste into X Articles. If images are missing, hover each one to copy it.",
            script=COPYABLE_SCRIPT,
            theme_overrides=_THEME,
        )
