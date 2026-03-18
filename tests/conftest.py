from __future__ import annotations

import pytest
from pathlib import Path
import nbformat

# ==============================================================================
# Global pytest configuration
# ==============================================================================


def pytest_configure(config):
    """Global pytest configuration - runs once at test session start."""
    # Set matplotlib backend to non-interactive
    import matplotlib

    matplotlib.use("Agg")

    # Suppress warnings from dependencies
    import warnings

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=PendingDeprecationWarning)


@pytest.fixture(autouse=True)
def reset_matplotlib():
    """Reset matplotlib/cache state between tests."""
    # Clear renderer caches so monkeypatch-based tests remain deterministic.
    from nb2wb.renderers import code_renderer, latex_renderer, table_renderer

    for name in ("_load_font", "_find_font", "_style_for_theme"):
        fn = getattr(code_renderer, name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()

    for name in ("_load_font", "_candidate_fonts"):
        fn = getattr(table_renderer, name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()

    for name in (
        "_matplotlib_module",
        "_matplotlib_colors",
        "_matplotlib_pyplot",
        "_tag_font",
    ):
        fn = getattr(latex_renderer, name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()
    clear_fn = getattr(latex_renderer, "_clear_render_cache", None)
    if clear_fn is not None:
        clear_fn()

    import matplotlib.pyplot as plt

    yield
    plt.close("all")


@pytest.fixture
def minimal_config():
    """Return minimal configuration for fast tests."""
    from nb2wb.config import Config, CodeConfig, LatexConfig

    return Config(
        image_width=800,
        border_radius=0,
        code=CodeConfig(
            font_size=24,
            theme="default",
            line_numbers=False,
            font="DejaVu Sans Mono",
            image_width=800,
            padding_x=10,
            padding_y=10,
            separator=10,
            background="#ffffff",
            border_radius=0,
        ),
        latex=LatexConfig(
            font_size=24,
            dpi=72,
            color="#000000",
            background="#ffffff",
            padding=10,
            image_width=800,
            try_usetex=False,  # Use mathtext for speed
            preamble="",
            border_radius=0,
        ),
    )


@pytest.fixture
def mock_latex_available(monkeypatch):
    """
    Mock LaTeX and dvipng being available.

    Creates fake DVI and PNG outputs for subprocess calls to latex and dvipng.
    """
    import subprocess
    from pathlib import Path

    def mock_run(cmd, **kwargs):
        """Mock subprocess.run for latex and dvipng commands."""
        if not cmd or len(cmd) == 0:

            class Result:
                returncode = 1
                stdout = b""
                stderr = b"Invalid command"

            return Result()

        # Handle latex command
        if cmd[0] == "latex" or (isinstance(cmd[0], Path) and cmd[0].name == "latex"):
            # Find output directory
            try:
                output_idx = cmd.index("-output-directory") + 1
                output_dir = Path(cmd[output_idx])
                dvi_path = output_dir / "formula.dvi"
                dvi_path.write_bytes(b"FAKE_DVI_FILE")
            except (ValueError, IndexError):
                pass

        # Handle dvipng command
        elif cmd[0] == "dvipng" or (
            isinstance(cmd[0], Path) and cmd[0].name == "dvipng"
        ):
            # Find output PNG path
            try:
                png_idx = cmd.index("-o") + 1
                png_path = Path(cmd[png_idx])
                # Create minimal 1x1 #ffffff PNG
                png_data = (
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                    b"\x00\x00\x00\nIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03"
                    b"\x00\x01\x8e\xea\xfe\x0e\x00\x00\x00\x00IEND\xaeB`\x82"
                )
                png_path.write_bytes(png_data)
            except (ValueError, IndexError):
                pass

        class Result:
            returncode = 0
            stdout = b""
            stderr = b""

        return Result()

    monkeypatch.setattr(subprocess, "run", mock_run)


@pytest.fixture
def mock_latex_unavailable(monkeypatch):
    """Mock LaTeX and dvipng being unavailable (not installed)."""
    import subprocess

    def mock_run(cmd, **kwargs):
        """Mock subprocess.run to simulate LaTeX not found."""
        raise FileNotFoundError("latex not found")

    monkeypatch.setattr(subprocess, "run", mock_run)


@pytest.fixture
def mock_font_available(monkeypatch):
    """Mock system font being available - returns mock font."""
    from PIL import ImageFont

    class MockFont:
        """Mock font object with minimal required interface."""

        def __init__(self, size=12):
            self.size = size
            self.font = self  # Self-reference for compatibility

        def getbbox(self, text, *args, **kwargs):
            """Return bounding box for text."""
            # Simple approximation: 10px width per char, height = size
            width = len(text) * 10
            return (0, 0, width, self.size)

        def getmask(self, text, *args, **kwargs):
            """Return mask for text rendering."""
            # Return a simple mock image core
            from PIL import Image

            width = len(text) * 10
            img = Image.new("L", (width, self.size), 255)
            return img.im  # Return the underlying C image object

        def getmask2(self, text, *args, **kwargs):
            """Return mask and offset for text rendering."""
            return self.getmask(text), (0, 0)

    def mock_truetype(path, size, *args, **kwargs):
        """Mock ImageFont.truetype to return mock font."""
        return MockFont(size)

    monkeypatch.setattr(ImageFont, "truetype", mock_truetype)


@pytest.fixture
def temp_md(tmp_path):
    """Write minimal .md file to temporary location and return path."""
    md_path = tmp_path / "test.md"
    md_path.write_text("# Test\n\nSome text.\n\n```python\nprint('hello')\n```\n")
    return md_path


@pytest.fixture
def md_with_directives(tmp_path):
    """Write .md file with nb2wb directives."""
    content = (
        "# Test\n\n"
        "<!-- nb2wb: hide-input -->\n"
        "```python\nprint('hidden source')\n```\n"
    )
    md_path = tmp_path / "directive_test.md"
    md_path.write_text(content)
    return md_path
