from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .api import (
    convert,
    load_input_payload,
    load_markdown_payload,
    load_notebook_payload,
    load_quarto_payload,
    supported_targets,
)
from .config import CodeConfig, Config, LatexConfig, SafetyConfig, TableConfig

try:
    __version__ = version("nb2wb")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "__version__",
    "CodeConfig",
    "Config",
    "LatexConfig",
    "TableConfig",
    "SafetyConfig",
    "convert",
    "load_input_payload",
    "load_notebook_payload",
    "load_markdown_payload",
    "load_quarto_payload",
    "supported_targets",
]
