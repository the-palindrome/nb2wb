"""
Shared pytest fixtures and configuration for nb2wb tests.

This module provides:
- Path fixtures for test data locations
- Configuration fixtures (default, minimal, platform-specific)
- Notebook fixtures (programmatically generated)
- Mock fixtures for external dependencies (LaTeX, fonts)
- Global pytest configuration
"""
from __future__ import annotations

import pytest
from pathlib import Path
from typing import TYPE_CHECKING
import nbformat

if TYPE_CHECKING:
    from nb2wb.config import Config


# ==============================================================================
# Global pytest configuration
# ==============================================================================

def pytest_configure(config):
    """Global pytest configuration - runs once at test session start."""
    # Set matplotlib backend to non-interactive
    import matplotlib
    matplotlib.use('Agg')

    # Suppress warnings from dependencies
    import warnings
    warnings.filterwarnings('ignore', category=DeprecationWarning)
    warnings.filterwarnings('ignore', category=PendingDeprecationWarning)


@pytest.fixture(autouse=True)
def reset_matplotlib():
    """Reset matplotlib state between tests."""
    import matplotlib.pyplot as plt
    yield
    plt.close('all')


# ==============================================================================
# Path fixtures
# ==============================================================================

@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def notebooks_dir(fixtures_dir):
    """Return path to test notebooks directory."""
    return fixtures_dir / "notebooks"


@pytest.fixture
def qmd_dir(fixtures_dir):
    """Return path to test .qmd files directory."""
    return fixtures_dir / "qmd"


@pytest.fixture
def configs_dir(fixtures_dir):
    """Return path to test config files directory."""
    return fixtures_dir / "configs"


@pytest.fixture
def images_dir(fixtures_dir):
    """Return path to test images directory."""
    return fixtures_dir / "images"


# ==============================================================================
# Configuration fixtures
# ==============================================================================

@pytest.fixture
def default_config():
    """Return default configuration."""
    from nb2wb.config import Config
    return Config()


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
            background="white",
            border_radius=0,
        ),
        latex=LatexConfig(
            font_size=24,
            dpi=72,
            color="black",
            background="white",
            padding=10,
            image_width=800,
            try_usetex=False,  # Use mathtext for speed
            preamble="",
            border_radius=0,
        ),
    )


@pytest.fixture
def x_platform_config():
    """Return X platform configuration."""
    from nb2wb.config import Config, apply_platform_defaults
    return apply_platform_defaults(Config(), "x")


# ==============================================================================
# Notebook fixtures (programmatically generated)
# ==============================================================================

@pytest.fixture
def minimal_notebook():
    """Return minimal test notebook with one markdown and one code cell."""
    nb = nbformat.v4.new_notebook()
    nb.metadata = {"kernelspec": {"name": "python3", "language": "python"}}
    nb.cells = [
        nbformat.v4.new_markdown_cell("# Test Notebook"),
        nbformat.v4.new_code_cell("print('hello')"),
    ]
    return nb


@pytest.fixture
def markdown_notebook():
    """Return notebook with only markdown cells."""
    nb = nbformat.v4.new_notebook()
    nb.metadata = {"kernelspec": {"name": "python3", "language": "python"}}
    nb.cells = [
        nbformat.v4.new_markdown_cell("# Heading"),
        nbformat.v4.new_markdown_cell("Paragraph with $x^2$ inline math."),
        nbformat.v4.new_markdown_cell("$$E = mc^2$$"),
    ]
    return nb


@pytest.fixture
def code_notebook():
    """Return notebook with only code cells."""
    nb = nbformat.v4.new_notebook()
    nb.metadata = {"kernelspec": {"name": "python3", "language": "python"}}

    cell1 = nbformat.v4.new_code_cell("x = 1 + 1")
    cell2 = nbformat.v4.new_code_cell("print(x)")
    cell2.outputs = [
        nbformat.v4.new_output(
            output_type="stream",
            name="stdout",
            text="2\n"
        )
    ]

    nb.cells = [cell1, cell2]
    return nb


@pytest.fixture
def tagged_notebook():
    """Return notebook with cell tags for visibility control."""
    nb = nbformat.v4.new_notebook()
    nb.metadata = {"kernelspec": {"name": "python3", "language": "python"}}

    # hide-cell: entire cell omitted
    cell1 = nbformat.v4.new_code_cell("secret = 42")
    cell1.metadata["tags"] = ["hide-cell"]

    # hide-input: only output shown
    cell2 = nbformat.v4.new_code_cell("print('output only')")
    cell2.metadata["tags"] = ["hide-input"]
    cell2.outputs = [
        nbformat.v4.new_output(
            output_type="stream",
            name="stdout",
            text="output only\n"
        )
    ]

    # hide-output: only source shown
    cell3 = nbformat.v4.new_code_cell("print('input only')")
    cell3.metadata["tags"] = ["hide-output"]
    cell3.outputs = [
        nbformat.v4.new_output(
            output_type="stream",
            name="stdout",
            text="input only\n"
        )
    ]

    nb.cells = [cell1, cell2, cell3]
    return nb


@pytest.fixture
def equation_numbered_notebook():
    """Return notebook with labeled equations for testing equation numbering."""
    nb = nbformat.v4.new_notebook()
    nb.metadata = {"kernelspec": {"name": "python3", "language": "python"}}
    nb.cells = [
        nbformat.v4.new_markdown_cell(
            r"$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a} \label{eq:quad}$$"
        ),
        nbformat.v4.new_markdown_cell(
            r"Reference to quadratic formula: \eqref{eq:quad}"
        ),
    ]
    return nb


@pytest.fixture
def latex_preamble_notebook():
    """Return notebook with LaTeX preamble cell."""
    nb = nbformat.v4.new_notebook()
    nb.metadata = {"kernelspec": {"name": "python3", "language": "python"}}

    # Preamble cell
    preamble_cell = nbformat.v4.new_markdown_cell(
        r"\usepackage{xcolor}\definecolor{myblue}{RGB}{0,100,200}"
    )
    preamble_cell.metadata["tags"] = ["latex-preamble"]

    # Cell using custom color
    equation_cell = nbformat.v4.new_markdown_cell(
        r"$$\color{myblue} E = mc^2$$"
    )

    nb.cells = [preamble_cell, equation_cell]
    return nb


# ==============================================================================
# Mock fixtures for external dependencies
# ==============================================================================

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
        elif cmd[0] == "dvipng" or (isinstance(cmd[0], Path) and cmd[0].name == "dvipng"):
            # Find output PNG path
            try:
                png_idx = cmd.index("-o") + 1
                png_path = Path(cmd[png_idx])
                # Create minimal 1x1 white PNG
                png_data = (
                    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
                    b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
                    b'\x00\x00\x00\nIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03'
                    b'\x00\x01\x8e\xea\xfe\x0e\x00\x00\x00\x00IEND\xaeB`\x82'
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
            img = Image.new('L', (width, self.size), 255)
            return img.im  # Return the underlying C image object

        def getmask2(self, text, *args, **kwargs):
            """Return mask and offset for text rendering."""
            return self.getmask(text), (0, 0)

    def mock_truetype(path, size, *args, **kwargs):
        """Mock ImageFont.truetype to return mock font."""
        return MockFont(size)

    monkeypatch.setattr(ImageFont, "truetype", mock_truetype)


# ==============================================================================
# Temporary file fixtures
# ==============================================================================

@pytest.fixture
def temp_notebook(tmp_path, minimal_notebook):
    """Write minimal notebook to temporary file and return path."""
    notebook_path = tmp_path / "test.ipynb"
    with open(notebook_path, "w") as f:
        nbformat.write(minimal_notebook, f)
    return notebook_path


@pytest.fixture
def temp_qmd(tmp_path):
    """Write minimal .qmd file to temporary location and return path."""
    qmd_path = tmp_path / "test.qmd"
    qmd_path.write_text("# Test\n\n```{python}\nprint('hello')\n```\n")
    return qmd_path


@pytest.fixture
def temp_md(tmp_path):
    """Write minimal .md file to temporary location and return path."""
    md_path = tmp_path / "test.md"
    md_path.write_text("# Test\n\nSome text.\n\n```python\nprint('hello')\n```\n")
    return md_path


@pytest.fixture
def md_with_preamble(tmp_path):
    """Write .md file with latex-preamble to temporary location."""
    content = (
        "# Test\n\n"
        "```latex-preamble\n"
        "\\usepackage{xcolor}\n"
        "\\definecolor{myblue}{RGB}{0,100,200}\n"
        "```\n\n"
        "$$\\color{myblue} E = mc^2$$\n"
    )
    md_path = tmp_path / "preamble_test.md"
    md_path.write_text(content)
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


@pytest.fixture
def temp_config(tmp_path):
    """Write minimal config to temporary file and return path."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("image_width: 1000\nborder_radius: 10\n")
    return config_path
