"""
Platform-specific HTML builders for different publishing platforms.
"""
from __future__ import annotations

from typing import Mapping

from .base import MIME_TO_EXT, PlatformBuilder
from .builder import ProfiledBuilder, TargetPageOptions, normalize_page_options
from .profiles import get_target_profile, list_target_keys


def get_builder(
    platform: str,
    *,
    target_options: Mapping[str, object] | TargetPageOptions | None = None,
) -> PlatformBuilder:
    """Construct the HTML builder for a publishing target.

    Args:
        platform: Publishing target key to build for.
        target_options: Optional per-target rendering overrides.

    Returns:
        A platform builder configured for the requested target.
    """
    profile = get_target_profile(platform)
    options = normalize_page_options(target_options)
    return ProfiledBuilder(profile, options=options)


def list_platforms() -> list[str]:
    """Return the canonical list of supported platform names.

    Args:
        None.

    Returns:
        Supported publishing target keys in stable order.
    """
    return list_target_keys()


__all__ = [
    "MIME_TO_EXT",
    "PlatformBuilder",
    "ProfiledBuilder",
    "TargetPageOptions",
    "get_builder",
    "list_platforms",
]
