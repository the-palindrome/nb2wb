"""
Backward-compatible Medium builder shim.

This module keeps the historical ``MediumBuilder`` class name while the
canonical implementation is profile-driven via ``ProfiledBuilder``.
"""
from __future__ import annotations

from .builder import ProfiledBuilder
from .profiles import get_target_profile


class MediumBuilder(ProfiledBuilder):
    """Compatibility wrapper for the Medium target profile."""

    def __init__(self) -> None:
        """Initialize the compatibility builder for Medium pages.

        Args:
            None.

        Returns:
            ``None``. The builder is configured with the Medium profile.
        """
        super().__init__(get_target_profile("medium"))
