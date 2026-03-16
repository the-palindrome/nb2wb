"""
Backward-compatible Substack builder shim.

This module keeps the historical ``SubstackBuilder`` class name while the
canonical implementation is profile-driven via ``ProfiledBuilder``.
"""
from __future__ import annotations

from .builder import ProfiledBuilder
from .profiles import get_target_profile


class SubstackBuilder(ProfiledBuilder):
    """Compatibility wrapper for the Substack target profile."""

    def __init__(self) -> None:
        """Initialize the compatibility builder for Substack pages.

        Args:
            None.

        Returns:
            ``None``. The builder is configured with the Substack profile.
        """
        super().__init__(get_target_profile("substack"))
