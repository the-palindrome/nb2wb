from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as pkg_version

project = "nb2wb"
author = "Tivadar Danka"

try:
    release = pkg_version("nb2wb")
except PackageNotFoundError:
    release = "0.0.0"
version = release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
]

html_theme = "furo"
html_static_path: list[str] = []
