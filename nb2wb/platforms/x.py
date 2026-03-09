"""
Backward-compatible X Articles builder shim.

This module keeps the historical ``XArticlesBuilder`` class name while the
canonical implementation is profile-driven via ``ProfiledBuilder``.
"""
from __future__ import annotations

from .builder import ProfiledBuilder
from .profiles import get_target_profile


class XArticlesBuilder(ProfiledBuilder):
    """Compatibility wrapper for the X target profile."""

    def __init__(self) -> None:
        super().__init__(get_target_profile("x"))

