from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, TypeVar

import yaml

from .platforms.builder import (
    TargetPageOptions,
    merge_page_options,
    normalize_page_options,
)
from .platforms.profiles import get_target_profile

_ConfigSection = TypeVar("_ConfigSection")


@dataclass
class CodeConfig:
    """Configuration for rendering code cells as syntax-highlighted PNG images."""

    font_size: int = 48
    theme: str = "monokai"
    line_numbers: bool = True
    font: str = "DejaVu Sans Mono"
    image_width: int = 1920
    padding_x: int = 100
    padding_y: int = 100
    separator: int = 0
    background: str = ""
    border_radius: int = 0


@dataclass
class LatexConfig:
    """Configuration for rendering display-math LaTeX blocks as PNG images."""

    font_size: int = 48
    dpi: int = 150
    color: str = "#000000"
    background: str = "#ffffff"
    padding: int = 68
    image_width: int = 1920
    try_usetex: bool = True
    preamble: str = ""
    cache_size: int = 256
    border_radius: int = 0


@dataclass
class TableConfig:
    """Configuration for rendering HTML/Markdown tables as PNG images."""

    mode: str = "native"
    font_size: int = 34
    font: str = "DejaVu Sans"
    color: str = "#1f2937"
    header_color: str = "#0f172a"
    background: str = "#ffffff"
    header_background: str = "#eef2ff"
    stripe_background: str = "#f8fafc"
    border_color: str = "#dbe4ee"
    border_width: int = 1
    cell_padding_x: int = 24
    cell_padding_y: int = 14
    outer_padding: int = 20
    canvas_background: str = "#ffffff"
    zebra_striping: bool = True
    shadow: bool = True
    shadow_color: str = "#0f172a"
    shadow_alpha: int = 24
    shadow_offset_x: int = 0
    shadow_offset_y: int = 8
    shadow_blur: int = 18
    image_width: int = 1920
    border_radius: int = 0


@dataclass
class SafetyConfig:
    """Security controls for untrusted server-side conversion workloads."""

    max_input_bytes: int = 20 * 1024 * 1024
    max_cells: int = 2000
    max_cell_source_chars: int = 500_000
    max_total_output_bytes: int = 25 * 1024 * 1024
    max_display_math_blocks: int = 500
    max_total_latex_chars: int = 1_000_000


@dataclass
class Config:
    """Top-level configuration aggregating render and safety settings."""

    image_width: int = 1920
    border_radius: int = 0
    code: CodeConfig = field(default_factory=CodeConfig)
    latex: LatexConfig = field(default_factory=LatexConfig)
    table: TableConfig = field(default_factory=TableConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    target_options: TargetPageOptions = field(default_factory=TargetPageOptions)


def load_config_from_dict(data: Mapping[str, Any] | None) -> Config:
    """Load config from an in-memory mapping using the YAML schema."""
    if data is None:
        return Config()
    if not isinstance(data, Mapping):
        raise TypeError("Config data must be a mapping (dict-like object).")
    return _build_config_from_mapping(data)


def load_config(path: Path | None) -> Config:
    """Load configuration from a YAML file, returning defaults when absent."""
    if path is None or not path.exists():
        return Config()
    return _build_config_from_mapping(_load_yaml_mapping(path))


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    """Read and validate the root YAML config mapping."""
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise TypeError("Config YAML root must be a mapping/object.")
    return data


def _build_config_from_mapping(data: Mapping[str, Any]) -> Config:
    """Build a ``Config`` object from a parsed config mapping."""
    top_width = data.get("image_width", Config.image_width)
    top_radius = data.get("border_radius", Config.border_radius)

    code_fields = _section_values(data, "code", CodeConfig)
    latex_fields = _section_values(data, "latex", LatexConfig)
    table_fields = _section_values(data, "table", TableConfig)
    safety_fields = _section_values(data, "safety", SafetyConfig)
    target_options = normalize_page_options(data.get("target_options"))

    for section_fields in (code_fields, latex_fields, table_fields):
        section_fields.setdefault("image_width", top_width)
        section_fields.setdefault("border_radius", top_radius)

    mode = str(table_fields.get("mode", TableConfig.mode)).strip().lower()
    table_fields["mode"] = mode if mode in {"native", "image"} else TableConfig.mode

    return Config(
        image_width=top_width,
        border_radius=top_radius,
        code=CodeConfig(**code_fields),
        latex=LatexConfig(**latex_fields),
        table=TableConfig(**table_fields),
        safety=SafetyConfig(**safety_fields),
        target_options=target_options,
    )


def resolve_target_options(
    config_target_options: TargetPageOptions | Mapping[str, Any] | None,
    runtime_target_options: TargetPageOptions | Mapping[str, Any] | None,
) -> TargetPageOptions:
    """Merge config and runtime target options with runtime precedence."""
    base = normalize_page_options(config_target_options)
    override = normalize_page_options(runtime_target_options)
    return merge_page_options(base, override)


def apply_target_profile_defaults(
    config: Config,
    platform: str,
    *,
    target_options: TargetPageOptions | Mapping[str, Any] | None = None,
) -> Config:
    """Apply target-profile render defaults to a config snapshot."""
    try:
        defaults = get_target_profile(platform).render_defaults
    except ValueError:
        return config

    options = normalize_page_options(target_options)
    code_overrides = defaults.get("code", {})
    latex_overrides = defaults.get("latex", {})
    table_overrides = defaults.get("table", {})
    if options.table_mode is not None:
        table_overrides = {**table_overrides, "mode": options.table_mode}

    return Config(
        image_width=defaults.get("image_width", config.image_width),
        border_radius=config.border_radius,
        code=CodeConfig(**_merged_section_values(config.code, code_overrides)),
        latex=LatexConfig(**_merged_section_values(config.latex, latex_overrides)),
        table=TableConfig(**_merged_section_values(config.table, table_overrides)),
        safety=config.safety,
        target_options=resolve_target_options(config.target_options, options),
    )


def _section_values(
    data: Mapping[str, Any],
    key: str,
    config_cls: type[_ConfigSection],
) -> dict[str, Any]:
    """Read one config section and keep only fields known to the dataclass."""
    raw = data.get(key, {})
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise TypeError(f"Config section '{key}' must be a mapping/object.")

    allowed = {field.name for field in fields(config_cls)}
    return {
        name: value
        for name, value in raw.items()
        if name in allowed
    }


def _merged_section_values(
    config_section: _ConfigSection,
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge overrides into a dataclass-backed config section."""
    values = {
        field.name: getattr(config_section, field.name)
        for field in fields(type(config_section))
    }
    values.update(overrides)
    return values
