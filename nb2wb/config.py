from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CodeConfig:
    font_size: int = 48
    theme: str = "monokai"
    line_numbers: bool = True
    font: str = "DejaVu Sans Mono"
    image_width: int = 1920  # minimum canvas width in pixels for rendered images
    padding_x: int = 100  # outer horizontal padding in pixels
    padding_y: int = 100  # outer vertical padding in pixels
    separator: int = 100  # gap in pixels between merged input/output blocks
    background: str = (
        "yellow"  # outer padding background colour; empty = use theme background
    )
    border_radius: int = 0  # corner radius in pixels (0 = square corners)


@dataclass
class LatexConfig:
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
class Config:
    image_width: int = 1920  # default canvas width for all rendered images
    border_radius: int = 0  # corner radius in pixels for all rendered images
    code: CodeConfig = field(default_factory=CodeConfig)
    latex: LatexConfig = field(default_factory=LatexConfig)


def load_config(path: Optional[Path]) -> Config:
    if path is None or not path.exists():
        return Config()

    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}

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

    # Sub-configs inherit top-level image_width / border_radius unless overridden
    code_fields.setdefault("image_width", top_width)
    latex_fields.setdefault("image_width", top_width)
    code_fields.setdefault("border_radius", top_radius)
    latex_fields.setdefault("border_radius", top_radius)

    return Config(
        image_width=top_width,
        border_radius=top_radius,
        code=CodeConfig(**code_fields),
        latex=LatexConfig(**latex_fields),
    )


def apply_platform_defaults(config: Config, platform: str) -> Config:
    """
    Apply platform-specific default adjustments to config.

    Returns a new Config with platform-optimized settings.
    """
    if platform == "x":
        # X Articles: much smaller images and fonts for 680px mobile-first content width
        return Config(
            image_width=680,
            border_radius=config.border_radius,
            code=CodeConfig(
                font_size=42,
                theme=config.code.theme,
                line_numbers=config.code.line_numbers,
                font=config.code.font,
                image_width=1200,
                padding_x=30,
                padding_y=30,
                separator=30,
                background=config.code.background,
                border_radius=config.code.border_radius,
            ),
            latex=LatexConfig(
                font_size=35,
                dpi=config.latex.dpi,
                color=config.latex.color,
                background=config.latex.background,
                padding=20,
                image_width=1200,
                try_usetex=config.latex.try_usetex,
                preamble=config.latex.preamble,
                border_radius=config.latex.border_radius,
            ),
        )
    # Default: return config unchanged (for Substack and others)
    return config
