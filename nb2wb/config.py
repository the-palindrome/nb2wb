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


@dataclass
class LatexConfig:
    font_size: int = 16
    dpi: int = 150
    color: str = "black"
    background: str = "white"
    padding: float = 0.15   # inches of padding around the expression
    try_usetex: bool = True  # try full LaTeX installation first


@dataclass
class Config:
    code: CodeConfig = field(default_factory=CodeConfig)
    latex: LatexConfig = field(default_factory=LatexConfig)


def load_config(path: Optional[Path]) -> Config:
    if path is None or not path.exists():
        return Config()

    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}

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

    return Config(
        code=CodeConfig(**code_fields),
        latex=LatexConfig(**latex_fields),
    )
