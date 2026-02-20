"""
Unit tests for the Markdown reader (nb2wb.md_reader).

Tests parsing of plain .md files into nbformat NotebookNode objects,
including code block extraction, language detection, latex-preamble blocks,
nb2wb HTML comment directives, front matter, and edge cases.
"""
import pytest
from pathlib import Path

from nb2wb.md_reader import read_md, _split_front_matter, _detect_language, _extract_cells, _consume_directives


# ==============================================================================
# Basic parsing
# ==============================================================================

class TestBasicParsing:
    """Test basic Markdown parsing into notebook cells."""

    def test_markdown_only(self, tmp_path):
        """A .md file with only prose produces only markdown cells."""
        md = tmp_path / "prose.md"
        md.write_text("# Heading\n\nSome paragraph text.\n")
        nb = read_md(md)
        assert len(nb.cells) == 1
        assert nb.cells[0].cell_type == "markdown"
        assert "Heading" in nb.cells[0].source

    def test_single_code_block(self, tmp_path):
        """A single fenced code block produces a markdown cell + code cell."""
        md = tmp_path / "single.md"
        md.write_text("# Title\n\n```python\nprint('hi')\n```\n")
        nb = read_md(md)
        assert len(nb.cells) == 2
        assert nb.cells[0].cell_type == "markdown"
        assert nb.cells[1].cell_type == "code"
        assert nb.cells[1].source == "print('hi')"

    def test_multiple_code_blocks(self, tmp_path):
        """Multiple code blocks interleaved with prose."""
        content = (
            "# Title\n\n"
            "```python\nx = 1\n```\n\n"
            "Some text.\n\n"
            "```python\ny = 2\n```\n"
        )
        md = tmp_path / "multi.md"
        md.write_text(content)
        nb = read_md(md)
        # Title -> code -> text -> code
        assert len(nb.cells) == 4
        assert nb.cells[0].cell_type == "markdown"
        assert nb.cells[1].cell_type == "code"
        assert nb.cells[1].source == "x = 1"
        assert nb.cells[2].cell_type == "markdown"
        assert nb.cells[3].cell_type == "code"
        assert nb.cells[3].source == "y = 2"

    def test_consecutive_code_blocks(self, tmp_path):
        """Two code blocks with no prose between them."""
        content = "```python\nx = 1\n```\n```python\ny = 2\n```\n"
        md = tmp_path / "consec.md"
        md.write_text(content)
        nb = read_md(md)
        assert len(nb.cells) == 2
        assert all(c.cell_type == "code" for c in nb.cells)

    def test_code_block_at_start(self, tmp_path):
        """Code block as the very first element (no leading prose)."""
        md = tmp_path / "start.md"
        md.write_text("```python\nprint('first')\n```\n\nTrailing text.\n")
        nb = read_md(md)
        assert nb.cells[0].cell_type == "code"
        assert nb.cells[1].cell_type == "markdown"

    def test_code_block_at_end(self, tmp_path):
        """Code block as the last element (no trailing prose)."""
        md = tmp_path / "end.md"
        md.write_text("Leading text.\n\n```python\nprint('last')\n```\n")
        nb = read_md(md)
        assert nb.cells[0].cell_type == "markdown"
        assert nb.cells[1].cell_type == "code"

    def test_empty_file(self, tmp_path):
        """An empty .md file produces an empty notebook."""
        md = tmp_path / "empty.md"
        md.write_text("")
        nb = read_md(md)
        assert len(nb.cells) == 0


# ==============================================================================
# Language detection
# ==============================================================================

class TestLanguageDetection:
    """Test language detection from code blocks and front matter."""

    def test_language_from_first_code_block(self, tmp_path):
        """Default language is inferred from the first code block."""
        md = tmp_path / "lang.md"
        md.write_text("```r\nsummary(iris)\n```\n")
        nb = read_md(md)
        assert nb.metadata["kernelspec"]["language"] == "r"

    def test_language_from_front_matter(self, tmp_path):
        """Front matter language key overrides code block detection."""
        content = "---\nlanguage: julia\n---\n\n```python\nprint('hi')\n```\n"
        md = tmp_path / "fm_lang.md"
        md.write_text(content)
        nb = read_md(md)
        assert nb.metadata["kernelspec"]["language"] == "julia"

    def test_language_default_python(self, tmp_path):
        """Default language is Python when no code blocks are present."""
        md = tmp_path / "no_code.md"
        md.write_text("# Just prose\n")
        nb = read_md(md)
        assert nb.metadata["kernelspec"]["language"] == "python"

    def test_per_cell_language_stored(self, tmp_path):
        """Each code cell stores its language in metadata."""
        content = "```python\nx = 1\n```\n\n```r\ny <- 2\n```\n"
        md = tmp_path / "mixed.md"
        md.write_text(content)
        nb = read_md(md)
        assert nb.cells[0].metadata["language"] == "python"
        assert nb.cells[1].metadata["language"] == "r"

    def test_code_block_without_language(self, tmp_path):
        """Untagged code block uses default language."""
        content = "```python\nfirst = 1\n```\n\n```\nplain text\n```\n"
        md = tmp_path / "nolang.md"
        md.write_text(content)
        nb = read_md(md)
        # First block sets default to python, second block has no lang
        assert nb.cells[1].metadata["language"] == "python"

    def test_latex_preamble_skipped_for_language_detection(self, tmp_path):
        """latex-preamble blocks are not used for language detection."""
        content = (
            "```latex-preamble\n\\usepackage{amsmath}\n```\n\n"
            "```r\nsummary(iris)\n```\n"
        )
        md = tmp_path / "skip.md"
        md.write_text(content)
        nb = read_md(md)
        assert nb.metadata["kernelspec"]["language"] == "r"


# ==============================================================================
# LaTeX preamble
# ==============================================================================

class TestLatexPreamble:
    """Test latex-preamble special code block handling."""

    def test_latex_preamble_block(self, tmp_path):
        """```latex-preamble block becomes a tagged markdown cell."""
        content = "```latex-preamble\n\\usepackage{xcolor}\n```\n"
        md = tmp_path / "preamble.md"
        md.write_text(content)
        nb = read_md(md)
        assert len(nb.cells) == 1
        assert nb.cells[0].cell_type == "markdown"
        assert "latex-preamble" in nb.cells[0].metadata.get("tags", [])
        assert nb.cells[0].source == "\\usepackage{xcolor}"

    def test_regular_latex_block(self, tmp_path):
        """```latex block becomes a regular code cell (not preamble)."""
        content = "```latex\nx = \\frac{a}{b}\n```\n"
        md = tmp_path / "latex.md"
        md.write_text(content)
        nb = read_md(md)
        assert len(nb.cells) == 1
        assert nb.cells[0].cell_type == "code"
        assert nb.cells[0].metadata["language"] == "latex"
        assert "latex-preamble" not in nb.cells[0].metadata.get("tags", [])

    def test_preamble_vs_latex_distinction(self, tmp_path):
        """Side-by-side: latex-preamble -> markdown cell, latex -> code cell."""
        content = (
            "```latex-preamble\n\\usepackage{amsmath}\n```\n\n"
            "```latex\nE = mc^2\n```\n"
        )
        md = tmp_path / "both.md"
        md.write_text(content)
        nb = read_md(md)
        assert nb.cells[0].cell_type == "markdown"
        assert "latex-preamble" in nb.cells[0].metadata["tags"]
        assert nb.cells[1].cell_type == "code"
        assert nb.cells[1].metadata["language"] == "latex"


# ==============================================================================
# Directives
# ==============================================================================

class TestDirectives:
    """Test HTML comment directive handling."""

    def test_hide_input_directive(self, tmp_path):
        """<!-- nb2wb: hide-input --> adds hide-input tag to next code block."""
        content = "<!-- nb2wb: hide-input -->\n```python\nprint('hi')\n```\n"
        md = tmp_path / "hide.md"
        md.write_text(content)
        nb = read_md(md)
        code_cell = [c for c in nb.cells if c.cell_type == "code"][0]
        assert "hide-input" in code_cell.metadata["tags"]

    def test_hide_output_directive(self, tmp_path):
        """<!-- nb2wb: hide-output --> adds hide-output tag."""
        content = "<!-- nb2wb: hide-output -->\n```python\nprint('hi')\n```\n"
        md = tmp_path / "hide_out.md"
        md.write_text(content)
        nb = read_md(md)
        code_cell = [c for c in nb.cells if c.cell_type == "code"][0]
        assert "hide-output" in code_cell.metadata["tags"]

    def test_hide_cell_directive(self, tmp_path):
        """<!-- nb2wb: hide-cell --> adds hide-cell tag."""
        content = "<!-- nb2wb: hide-cell -->\n```python\nprint('hi')\n```\n"
        md = tmp_path / "hide_cell.md"
        md.write_text(content)
        nb = read_md(md)
        code_cell = [c for c in nb.cells if c.cell_type == "code"][0]
        assert "hide-cell" in code_cell.metadata["tags"]

    def test_multiple_tags_one_comment(self, tmp_path):
        """Multiple tags in one comment: <!-- nb2wb: hide-input, hide-output -->."""
        content = "<!-- nb2wb: hide-input, hide-output -->\n```python\nprint('hi')\n```\n"
        md = tmp_path / "multi_tag.md"
        md.write_text(content)
        nb = read_md(md)
        code_cell = [c for c in nb.cells if c.cell_type == "code"][0]
        assert "hide-input" in code_cell.metadata["tags"]
        assert "hide-output" in code_cell.metadata["tags"]

    def test_multiple_comments(self, tmp_path):
        """Two separate comments before one block are merged."""
        content = (
            "<!-- nb2wb: hide-input -->\n"
            "<!-- nb2wb: hide-output -->\n"
            "```python\nprint('hi')\n```\n"
        )
        md = tmp_path / "multi_comment.md"
        md.write_text(content)
        nb = read_md(md)
        code_cell = [c for c in nb.cells if c.cell_type == "code"][0]
        assert "hide-input" in code_cell.metadata["tags"]
        assert "hide-output" in code_cell.metadata["tags"]

    def test_directive_removed_from_prose(self, tmp_path):
        """Directives are removed from markdown cell text."""
        content = (
            "Some text.\n\n"
            "<!-- nb2wb: hide-input -->\n"
            "```python\nprint('hi')\n```\n"
        )
        md = tmp_path / "removed.md"
        md.write_text(content)
        nb = read_md(md)
        md_cells = [c for c in nb.cells if c.cell_type == "markdown"]
        for cell in md_cells:
            assert "nb2wb" not in cell.source
            assert "<!--" not in cell.source

    def test_directive_not_followed_by_code(self, tmp_path):
        """Trailing directive without following code block is silently discarded."""
        content = "Some text.\n\n<!-- nb2wb: hide-input -->\n"
        md = tmp_path / "trailing.md"
        md.write_text(content)
        nb = read_md(md)
        assert len(nb.cells) == 1
        assert nb.cells[0].cell_type == "markdown"

    def test_no_directive(self, tmp_path):
        """Code block without directive has no tags."""
        content = "```python\nprint('hi')\n```\n"
        md = tmp_path / "no_dir.md"
        md.write_text(content)
        nb = read_md(md)
        code_cell = nb.cells[0]
        assert code_cell.metadata.get("tags") is None or len(code_cell.metadata.get("tags", [])) == 0


# ==============================================================================
# Fence-line tags
# ==============================================================================

class TestFenceLineTags:
    """Test tags specified directly on the code fence line."""

    def test_single_fence_tag(self, tmp_path):
        """```python hide-input adds hide-input tag."""
        content = "```python hide-input\nprint('hi')\n```\n"
        md = tmp_path / "fence_tag.md"
        md.write_text(content)
        nb = read_md(md)
        code_cell = nb.cells[0]
        assert "hide-input" in code_cell.metadata["tags"]
        assert code_cell.metadata["language"] == "python"

    def test_multiple_fence_tags(self, tmp_path):
        """```python hide-input hide-output adds both tags."""
        content = "```python hide-input hide-output\nprint('hi')\n```\n"
        md = tmp_path / "fence_multi.md"
        md.write_text(content)
        nb = read_md(md)
        code_cell = nb.cells[0]
        assert "hide-input" in code_cell.metadata["tags"]
        assert "hide-output" in code_cell.metadata["tags"]

    def test_fence_tag_hide_cell(self, tmp_path):
        """```python hide-cell adds hide-cell tag."""
        content = "```python hide-cell\nprint('hi')\n```\n"
        md = tmp_path / "fence_hide.md"
        md.write_text(content)
        nb = read_md(md)
        code_cell = nb.cells[0]
        assert "hide-cell" in code_cell.metadata["tags"]

    def test_fence_tags_combined_with_directive(self, tmp_path):
        """Fence-line tags and HTML comment directives are merged."""
        content = "<!-- nb2wb: hide-output -->\n```python hide-input\nprint('hi')\n```\n"
        md = tmp_path / "fence_combo.md"
        md.write_text(content)
        nb = read_md(md)
        code_cell = nb.cells[0]
        assert "hide-input" in code_cell.metadata["tags"]
        assert "hide-output" in code_cell.metadata["tags"]

    def test_latex_with_fence_tag(self, tmp_path):
        """```latex hide-input adds tag to latex code cell."""
        content = "```latex hide-input\n\\frac{a}{b}\n```\n"
        md = tmp_path / "latex_tag.md"
        md.write_text(content)
        nb = read_md(md)
        code_cell = nb.cells[0]
        assert code_cell.metadata["language"] == "latex"
        assert "hide-input" in code_cell.metadata["tags"]

    def test_fence_tag_with_tilde(self, tmp_path):
        """~~~python hide-input also works with tilde fences."""
        content = "~~~python hide-input\nprint('hi')\n~~~\n"
        md = tmp_path / "tilde_tag.md"
        md.write_text(content)
        nb = read_md(md)
        code_cell = nb.cells[0]
        assert "hide-input" in code_cell.metadata["tags"]

    def test_no_fence_tags(self, tmp_path):
        """Code block with only language has no fence-line tags."""
        content = "```python\nprint('hi')\n```\n"
        md = tmp_path / "no_fence_tag.md"
        md.write_text(content)
        nb = read_md(md)
        code_cell = nb.cells[0]
        assert not code_cell.metadata.get("tags")


# ==============================================================================
# Front matter
# ==============================================================================

class TestFrontMatter:
    """Test YAML front matter parsing."""

    def test_yaml_front_matter_parsed(self, tmp_path):
        """Front matter is extracted and removed from body."""
        content = "---\ntitle: Test\nlanguage: r\n---\n\n# Heading\n"
        md = tmp_path / "fm.md"
        md.write_text(content)
        nb = read_md(md)
        assert nb.metadata["kernelspec"]["language"] == "r"
        # Front matter should not appear in cell text
        assert "---" not in nb.cells[0].source

    def test_no_front_matter(self, tmp_path):
        """File without front matter works normally."""
        md = tmp_path / "no_fm.md"
        md.write_text("# Heading\n\nText.\n")
        nb = read_md(md)
        assert len(nb.cells) == 1
        assert nb.metadata["kernelspec"]["language"] == "python"

    def test_invalid_yaml_front_matter(self, tmp_path):
        """Malformed YAML in front matter is treated as empty."""
        content = "---\n: invalid: yaml: [[\n---\n\n# Heading\n"
        md = tmp_path / "bad_fm.md"
        md.write_text(content)
        nb = read_md(md)
        # Should not crash, defaults to python
        assert nb.metadata["kernelspec"]["language"] == "python"


# ==============================================================================
# Edge cases
# ==============================================================================

class TestEdgeCases:
    """Test edge cases in Markdown parsing."""

    def test_tilde_fenced_blocks(self, tmp_path):
        """~~~ fences work the same as ``` fences."""
        content = "~~~python\nprint('hi')\n~~~\n"
        md = tmp_path / "tilde.md"
        md.write_text(content)
        nb = read_md(md)
        assert len(nb.cells) == 1
        assert nb.cells[0].cell_type == "code"
        assert nb.cells[0].source == "print('hi')"

    def test_four_backtick_fence(self, tmp_path):
        """Four-backtick fences work."""
        content = "````python\nprint('hi')\n````\n"
        md = tmp_path / "four.md"
        md.write_text(content)
        nb = read_md(md)
        assert len(nb.cells) == 1
        assert nb.cells[0].cell_type == "code"

    def test_whitespace_in_code_blocks(self, tmp_path):
        """Leading/trailing whitespace in code blocks is stripped."""
        content = "```python\n\n  x = 1\n\n```\n"
        md = tmp_path / "ws.md"
        md.write_text(content)
        nb = read_md(md)
        assert nb.cells[0].source == "x = 1"

    def test_only_front_matter(self, tmp_path):
        """File with only front matter and no body."""
        content = "---\nlanguage: r\n---\n"
        md = tmp_path / "only_fm.md"
        md.write_text(content)
        nb = read_md(md)
        assert len(nb.cells) == 0
        assert nb.metadata["kernelspec"]["language"] == "r"


# ==============================================================================
# Helper function unit tests
# ==============================================================================

class TestSplitFrontMatter:
    """Test the _split_front_matter helper."""

    def test_extracts_front_matter(self):
        fm, body = _split_front_matter("---\nkey: value\n---\nBody text.\n")
        assert fm == {"key": "value"}
        assert body == "Body text.\n"

    def test_no_front_matter(self):
        fm, body = _split_front_matter("Just text.\n")
        assert fm == {}
        assert body == "Just text.\n"


class TestConsumeDirectives:
    """Test the _consume_directives helper."""

    def test_removes_directive(self):
        tags: list[str] = []
        result = _consume_directives("before\n<!-- nb2wb: hide-input -->\nafter", tags)
        assert "hide-input" in tags
        assert "nb2wb" not in result
        assert "before" in result
        assert "after" in result

    def test_multiple_tags(self):
        tags: list[str] = []
        _consume_directives("<!-- nb2wb: tag1, tag2 -->", tags)
        assert tags == ["tag1", "tag2"]

    def test_no_directives(self):
        tags: list[str] = []
        result = _consume_directives("plain text", tags)
        assert tags == []
        assert result == "plain text"
