from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("nb2wb")
except PackageNotFoundError:
    __version__ = "0.0.0"
