from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CodeConfig:
    font_size: int = 14
    theme: str = "monokai"
    line_numbers: bool = True
    font: str = "DejaVu Sans Mono"
    image_width: int = 1920  # minimum canvas width in pixels for rendered images
    padding_x: int = 0       # outer horizontal padding in pixels
    padding_y: int = 0       # outer vertical padding in pixels
    separator: int = 0       # gap in pixels between merged input/output blocks
    background: str = ""     # outer padding background colour; empty = use theme background


@dataclass
class LatexConfig:
    font_size: int = 48
    dpi: int = 150
    color: str = "black"
    background: str = "white"
    padding: int = 68        # vertical padding in pixels around the expression
    image_width: int = 1920  # canvas width in pixels for rendered images
    try_usetex: bool = True  # try full LaTeX installation first


@dataclass
class Config:
    image_width: int = 1920  # default canvas width for all rendered images
    code: CodeConfig = field(default_factory=CodeConfig)
    latex: LatexConfig = field(default_factory=LatexConfig)


def load_config(path: Optional[Path]) -> Config:
    if path is None or not path.exists():
        return Config()

    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}

    top_width = data.get("image_width", 1920)

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

    # Sub-configs inherit the top-level image_width unless explicitly overridden
    code_fields.setdefault("image_width", top_width)
    latex_fields.setdefault("image_width", top_width)

    return Config(
        image_width=top_width,
        code=CodeConfig(**code_fields),
        latex=LatexConfig(**latex_fields),
    )
