"""
Platform-specific HTML builders for different publishing platforms.
"""
from __future__ import annotations

from .base import PlatformBuilder
from .substack import SubstackBuilder
from .x import XArticlesBuilder


_BUILDERS: dict[str, type[PlatformBuilder]] = {
    "substack": SubstackBuilder,
    "x": XArticlesBuilder,
}


def get_builder(platform: str) -> PlatformBuilder:
    """Get the appropriate HTML builder for the specified platform."""
    if platform not in _BUILDERS:
        raise ValueError(
            f"Unknown platform: {platform}. Supported: {list(_BUILDERS.keys())}"
        )
    return _BUILDERS[platform]()


def list_platforms() -> list[str]:
    """Return list of supported platform names."""
    return list(_BUILDERS.keys())


__all__ = ["PlatformBuilder", "get_builder", "list_platforms"]
