from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .api import convert, supported_targets
from .config import CodeConfig, Config, LatexConfig, SafetyConfig

try:
    __version__ = version("nb2wb")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "__version__",
    "CodeConfig",
    "Config",
    "LatexConfig",
    "SafetyConfig",
    "convert",
    "supported_targets",
]
