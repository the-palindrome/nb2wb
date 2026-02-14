"""
Abstract base class for platform-specific HTML builders.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class PlatformBuilder(ABC):
    """
    Base class for platform-specific HTML builders.

    Each platform has different requirements for HTML structure, CSS styling,
    and interactive features. Subclasses implement platform-specific rendering.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable platform name."""
        pass

    @abstractmethod
    def build_page(self, content_html: str) -> str:
        """
        Wrap converted cell content in a complete HTML page.

        Args:
            content_html: HTML fragments from converted notebook cells

        Returns:
            Complete HTML document ready for the platform
        """
        pass
