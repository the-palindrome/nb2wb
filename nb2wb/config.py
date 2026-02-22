from __future__ import annotations

import yaml
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from typing import Optional


@dataclass
class CodeConfig:
    """Configuration for rendering code cells as syntax-highlighted PNG images."""

    font_size: int = 48
    theme: str = "monokai"
    line_numbers: bool = True
    font: str = "DejaVu Sans Mono"
    image_width: int = 1920  # minimum canvas width in pixels for rendered images
    padding_x: int = 100  # outer horizontal padding in pixels
    padding_y: int = 100  # outer vertical padding in pixels
    separator: int = 0  # gap in pixels between merged input/output blocks
    background: str = (
        ""  # outer padding background colour; empty = use theme background
    )
    border_radius: int = 14  # corner radius in pixels (0 = square corners)


@dataclass
class LatexConfig:
    """Configuration for rendering display-math LaTeX blocks as PNG images."""

    font_size: int = 48
    dpi: int = 150
    color: str = "black"
    background: str = "white"
    padding: int = 68  # vertical padding in pixels around the expression
    image_width: int = 1920  # canvas width in pixels for rendered images
    try_usetex: bool = True  # try full LaTeX installation first
    preamble: str = ""  # extra LaTeX preamble (appended after builtins)
    border_radius: int = 0  # corner radius in pixels (0 = square corners)


@dataclass
class TableConfig:
    """Configuration for rendering HTML/Markdown tables as PNG images."""

    mode: str = "native"  # "native" keeps HTML tables, "image" renders tables to PNG
    font_size: int = 34
    font: str = "DejaVu Sans"
    color: str = "#222222"
    header_color: str = "#111111"
    background: str = "white"
    header_background: str = "#f4f4f4"
    border_color: str = "#d9d9d9"
    border_width: int = 1
    cell_padding_x: int = 20
    cell_padding_y: int = 12
    image_width: int = 1920  # canvas width in pixels for rendered table images
    border_radius: int = 0  # corner radius in pixels (0 = square corners)


@dataclass
class SafetyConfig:
    """Security controls for untrusted server-side conversion workloads."""

    max_input_bytes: int = 20 * 1024 * 1024  # max input document size
    max_cells: int = 2000  # max number of notebook cells
    max_cell_source_chars: int = 500_000  # max chars in any single cell source
    max_total_output_bytes: int = 25 * 1024 * 1024  # max aggregate output payload
    max_display_math_blocks: int = 500  # max number of display-math blocks rendered
    max_total_latex_chars: int = (
        1_000_000  # max aggregate chars across display-math blocks
    )


@dataclass
class Config:
    """Top-level configuration aggregating render and safety settings."""

    image_width: int = 1920  # default canvas width for all rendered images
    border_radius: int = 14  # corner radius in pixels for all rendered images
    code: CodeConfig = field(default_factory=CodeConfig)
    latex: LatexConfig = field(default_factory=LatexConfig)
    table: TableConfig = field(default_factory=TableConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)


def load_config_from_dict(data: Mapping[str, Any] | None) -> Config:
    """Load config from an in-memory mapping using the same schema as YAML config files."""
    if data is None:
        return Config()
    if not isinstance(data, Mapping):
        raise TypeError("Config data must be a mapping (dict-like object).")

    # Copy to a plain dict so .get() behavior is predictable even for custom mappings.
    raw: dict[str, Any] = dict(data)
    return _build_config_from_mapping(raw)


def load_config(path: Optional[Path]) -> Config:
    """Load configuration from a YAML file, returning defaults if *path* is None or missing.

    Sub-configs (code, latex, table) inherit the top-level ``image_width`` and
    ``border_radius`` unless explicitly overridden in the YAML.
    """
    if path is None or not path.exists():
        return Config()

    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise TypeError("Config YAML root must be a mapping/object.")

    return _build_config_from_mapping(data)


def _build_config_from_mapping(data: dict[str, Any]) -> Config:
    """Build Config from a parsed config mapping."""
    top_width = data.get("image_width", 1920)
    top_radius = data.get("border_radius", 0)

    code_fields = {
        k: v
        for k, v in data.get("code", {}).items()
        if k in CodeConfig.__dataclass_fields__
    }
    latex_fields = {
        k: v
        for k, v in data.get("latex", {}).items()
        if k in LatexConfig.__dataclass_fields__
    }
    table_fields = {
        k: v
        for k, v in data.get("table", {}).items()
        if k in TableConfig.__dataclass_fields__
    }
    safety_fields = {
        k: v
        for k, v in data.get("safety", {}).items()
        if k in SafetyConfig.__dataclass_fields__
    }

    # Sub-configs inherit top-level image_width / border_radius unless overridden
    code_fields.setdefault("image_width", top_width)
    latex_fields.setdefault("image_width", top_width)
    table_fields.setdefault("image_width", top_width)
    code_fields.setdefault("border_radius", top_radius)
    latex_fields.setdefault("border_radius", top_radius)
    table_fields.setdefault("border_radius", top_radius)

    mode = str(table_fields.get("mode", TableConfig.mode)).strip().lower()
    table_fields["mode"] = mode if mode in {"native", "image"} else TableConfig.mode

    return Config(
        image_width=top_width,
        border_radius=top_radius,
        code=CodeConfig(**code_fields),
        latex=LatexConfig(**latex_fields),
        table=TableConfig(**table_fields),
        safety=SafetyConfig(**safety_fields),
    )


# Platform-specific default overrides.  Only the fields listed here are
# changed; everything else is inherited from the user's config.
_PLATFORM_DEFAULTS: dict[str, dict] = {
    "substack": {
        "table": {"mode": "image"},
    },
    "x": {
        "image_width": 680,
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
        },
    },
    "medium": {
        "image_width": 700,
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
        },
    },
}


def apply_platform_defaults(config: Config, platform: str) -> Config:
    """
    Apply platform-specific default adjustments to config.

    Returns a new Config with platform-optimized settings.
    """
    defaults = _PLATFORM_DEFAULTS.get(platform)
    if defaults is None:
        return config

    code_overrides = defaults.get("code", {})
    latex_overrides = defaults.get("latex", {})
    table_overrides = defaults.get("table", {})

    # Build CodeConfig: start from current config, override with platform defaults
    code_fields = {f: getattr(config.code, f) for f in CodeConfig.__dataclass_fields__}
    code_fields.update(code_overrides)

    # Build LatexConfig: start from current config, override with platform defaults
    latex_fields = {
        f: getattr(config.latex, f) for f in LatexConfig.__dataclass_fields__
    }
    latex_fields.update(latex_overrides)
    table_fields = {
        f: getattr(config.table, f) for f in TableConfig.__dataclass_fields__
    }
    table_fields.update(table_overrides)

    return Config(
        image_width=defaults.get("image_width", config.image_width),
        border_radius=config.border_radius,
        code=CodeConfig(**code_fields),
        latex=LatexConfig(**latex_fields),
        table=TableConfig(**table_fields),
        safety=config.safety,
    )
