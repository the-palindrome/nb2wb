"""
Declarative target profiles for platform wrappers and render defaults.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ImageStrategy = str
CopyScriptMode = str

IMAGE_STRATEGIES = frozenset({"embed", "copyable", "preserve"})
COPY_SCRIPT_MODES = frozenset({"simple", "copyable", "none"})


@dataclass(frozen=True)
class TargetProfile:
    """Static defaults for one publishing target."""

    key: str
    name: str
    title: str
    toolbar_message: str
    theme_overrides: dict[str, str] = field(default_factory=dict)
    extra_css: str = ""
    image_strategy: ImageStrategy = "embed"
    raw_image_strategy: ImageStrategy = "embed"
    copy_script_mode: CopyScriptMode = "simple"
    render_defaults: dict[str, Any] = field(default_factory=dict)


def get_target_profile(key: str) -> TargetProfile:
    """Return profile for *key* or raise ValueError with supported keys."""
    profile = TARGET_PROFILES.get(key)
    if profile is None:
        raise ValueError(
            f"Unknown platform: {key}. Supported: {list(TARGET_PROFILES.keys())}"
        )
    return profile


def list_target_keys() -> list[str]:
    """Return canonical target keys in stable order."""
    return list(TARGET_PROFILES.keys())


_THEME_SUBSTACK = {
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
}

_THEME_MEDIUM = {
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
    "copy-image-button-background": "rgba(26, 137, 23, 0.9)",
    "copy-image-button-hover-background": "rgba(13, 95, 11, 0.95)",
    "copy-image-button-copied-background": "#0d5f0b",
}

_THEME_X = {
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
    "copy-image-button-background": "rgba(29, 155, 240, 0.9)",
    "copy-image-button-hover-background": "rgba(20, 120, 190, 0.95)",
    "copy-image-button-copied-background": "#1478be",
}

_THEME_LINKEDIN = {
    **_THEME_X,
    "body-max-width": "760px",
    "body-font-size": "18px",
    "toolbar-background": "#0a66c2",
    "toolbar-button-color": "#0a66c2",
    "toolbar-button-hover-background": "#e8f3ff",
    "copy-image-button-background": "rgba(10, 102, 194, 0.92)",
    "copy-image-button-hover-background": "rgba(8, 82, 156, 0.95)",
    "copy-image-button-copied-background": "#08529c",
}

_THEME_DEVTO = {
    **_THEME_SUBSTACK,
    "body-max-width": "860px",
    "body-background": "#f5f5f5",
    "toolbar-background": "#0a0a0a",
    "toolbar-color": "#f7f7f7",
    "toolbar-button-background": "#3b49df",
    "toolbar-button-color": "#fff",
    "toolbar-button-hover-background": "#2f3bc4",
}

_THEME_HASHNODE = {
    **_THEME_SUBSTACK,
    "body-max-width": "840px",
    "body-background": "#ffffff",
    "toolbar-background": "#2962ff",
    "toolbar-color": "#ffffff",
    "toolbar-button-background": "#ffffff",
    "toolbar-button-color": "#2962ff",
    "toolbar-button-hover-background": "#eef3ff",
}

_THEME_GHOST = {
    **_THEME_SUBSTACK,
    "body-max-width": "900px",
    "body-background": "#f8f8f8",
    "toolbar-background": "#15171a",
    "toolbar-color": "#ffffff",
    "toolbar-button-background": "#ffffff",
    "toolbar-button-color": "#15171a",
    "toolbar-button-hover-background": "#ececec",
}

_THEME_WORDPRESS = {
    **_THEME_SUBSTACK,
    "body-max-width": "920px",
    "body-background": "#f6f7f7",
    "toolbar-background": "#3858e9",
    "toolbar-color": "#ffffff",
    "toolbar-button-background": "#ffffff",
    "toolbar-button-color": "#3858e9",
    "toolbar-button-hover-background": "#edf1ff",
}

_EXTRA_CSS_SUBSTACK = """\
    #toolbar p { opacity: 0.7; }
    ul, ol { padding-left: 1.6em; }
    li { margin-bottom: 0.25em; }
"""

_NARROW_RENDER_DEFAULTS = {
    "code": {
        "font_size": 42,
        "image_width": 1200,
        "padding_x": 30,
        "padding_y": 30,
        "separator": 0,
    },
    "latex": {"font_size": 35, "padding": 50, "image_width": 1200},
    "table": {
        "mode": "image",
        "font_size": 30,
        "image_width": 1200,
        "cell_padding_x": 16,
        "cell_padding_y": 10,
        "border_radius": 10,
        "shadow_alpha": 20,
        "shadow_blur": 14,
        "shadow_offset_y": 6,
    },
}

TARGET_PROFILES: dict[str, TargetProfile] = {
    "substack": TargetProfile(
        key="substack",
        name="Substack",
        title="nb2wb — Substack Preview",
        toolbar_message="Then paste directly into your Substack draft.",
        theme_overrides=_THEME_SUBSTACK,
        extra_css=_EXTRA_CSS_SUBSTACK,
        image_strategy="embed",
        raw_image_strategy="embed",
        copy_script_mode="simple",
        render_defaults={
            "table": {
                "mode": "image",
                "border_radius": 12,
                "outer_padding": 20,
            },
        },
    ),
    "medium": TargetProfile(
        key="medium",
        name="Medium",
        title="nb2wb — Medium Preview",
        toolbar_message="Paste into Medium. If images are missing, hover each one to copy it.",
        theme_overrides=_THEME_MEDIUM,
        image_strategy="copyable",
        raw_image_strategy="embed",
        copy_script_mode="copyable",
        render_defaults={
            "image_width": 700,
            **_NARROW_RENDER_DEFAULTS,
            "table": {
                **_NARROW_RENDER_DEFAULTS["table"],
                "outer_padding": 16,
            },
        },
    ),
    "x": TargetProfile(
        key="x",
        name="X Articles",
        title="nb2wb — X Articles Preview",
        toolbar_message="Paste into X Articles. If images are missing, hover each one to copy it.",
        theme_overrides=_THEME_X,
        image_strategy="copyable",
        raw_image_strategy="embed",
        copy_script_mode="copyable",
        render_defaults={
            "image_width": 680,
            **_NARROW_RENDER_DEFAULTS,
            "table": {
                **_NARROW_RENDER_DEFAULTS["table"],
                "outer_padding": 14,
            },
        },
    ),
    "linkedin": TargetProfile(
        key="linkedin",
        name="LinkedIn Articles",
        title="nb2wb — LinkedIn Preview",
        toolbar_message="Paste into a LinkedIn article. If images are missing, hover each one to copy it.",
        theme_overrides=_THEME_LINKEDIN,
        image_strategy="copyable",
        raw_image_strategy="embed",
        copy_script_mode="copyable",
        render_defaults={
            "image_width": 760,
            **_NARROW_RENDER_DEFAULTS,
            "table": {
                **_NARROW_RENDER_DEFAULTS["table"],
                "outer_padding": 18,
            },
        },
    ),
    "devto": TargetProfile(
        key="devto",
        name="Dev.to",
        title="nb2wb — Dev.to Preview",
        toolbar_message="Paste directly into a Dev.to article draft.",
        theme_overrides=_THEME_DEVTO,
        image_strategy="embed",
        raw_image_strategy="embed",
        copy_script_mode="simple",
        render_defaults={
            "image_width": 860,
            "table": {"mode": "image", "border_radius": 10, "outer_padding": 18},
        },
    ),
    "hashnode": TargetProfile(
        key="hashnode",
        name="Hashnode",
        title="nb2wb — Hashnode Preview",
        toolbar_message="Paste directly into a Hashnode draft.",
        theme_overrides=_THEME_HASHNODE,
        image_strategy="embed",
        raw_image_strategy="embed",
        copy_script_mode="simple",
        render_defaults={
            "image_width": 840,
            "table": {"mode": "image", "border_radius": 10, "outer_padding": 18},
        },
    ),
    "ghost": TargetProfile(
        key="ghost",
        name="Ghost",
        title="nb2wb — Ghost Preview",
        toolbar_message="Paste directly into your Ghost editor.",
        theme_overrides=_THEME_GHOST,
        image_strategy="embed",
        raw_image_strategy="embed",
        copy_script_mode="simple",
        render_defaults={
            "image_width": 900,
            "table": {"mode": "image", "border_radius": 10, "outer_padding": 18},
        },
    ),
    "wordpress": TargetProfile(
        key="wordpress",
        name="WordPress",
        title="nb2wb — WordPress Preview",
        toolbar_message="Paste directly into the WordPress block editor.",
        theme_overrides=_THEME_WORDPRESS,
        image_strategy="embed",
        raw_image_strategy="embed",
        copy_script_mode="simple",
        render_defaults={
            "image_width": 920,
            "table": {"mode": "image", "border_radius": 10, "outer_padding": 18},
        },
    ),
}

