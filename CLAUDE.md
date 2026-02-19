# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

nb2wb (notebook to web) converts Jupyter Notebooks and Quarto (.qmd) files into self-contained HTML files for publishing on Substack, Medium, and X Articles. It renders LaTeX as PNGs, converts inline math to Unicode, and syntax-highlights code cells as images — all base64-embedded so the HTML has no external dependencies.

## Commands

### Install for development
```bash
pip install -e ".[dev]"
```

### Run the tool
```bash
nb2wb notebook.ipynb                    # Substack (default)
nb2wb notebook.ipynb -t medium          # Medium format
nb2wb notebook.ipynb -t x              # X Articles format
nb2wb notebook.ipynb -c config.yaml    # Custom config
```

### Tests
```bash
pytest                                  # Full suite
pytest tests/unit/                      # Unit tests only
pytest tests/integration/               # Integration tests only
pytest tests/unit/test_inline_latex.py  # Single test file
pytest -k "test_name"                   # Single test by name
pytest -m "not latex"                   # Skip tests requiring LaTeX+dvipng
```

### Lint
```bash
black nb2wb/ tests/
isort nb2wb/ tests/
```

### Build
```bash
pip install build && python -m build
```

## Architecture

### Conversion Pipeline

```
.ipynb / .qmd
    │
    ▼
 read (nbformat / qmd_reader)
    │
    ▼
 Converter.convert()
    ├── Markdown cells: protect code → resolve \eqref → display math→PNG
    │                   → inline math→Unicode → Markdown→HTML
    └── Code cells: source→PNG → outputs→PNG/embed → vstack
    │
    ▼
 PlatformBuilder.build_page()
    ├── Substack: base64 images, single copy button
    ├── Medium:   per-image copy buttons, optional --serve
    └── X:        per-image copy buttons
    │
    ▼
 Final self-contained HTML
```

### Directory Structure

```
nb2wb/
├── __init__.py              # Package init (__version__)
├── __main__.py              # python -m nb2wb entry point
├── cli.py                   # CLI argument parsing & serve mode
├── config.py                # YAML config loading, dataclasses
├── converter.py             # Main conversion pipeline orchestrator
├── qmd_reader.py            # Quarto .qmd file parser
├── platforms/
│   ├── __init__.py          # get_builder() / list_platforms()
│   ├── base.py              # Abstract PlatformBuilder base class
│   ├── substack.py          # Substack HTML builder
│   ├── medium.py            # Medium HTML builder
│   └── x.py                 # X Articles HTML builder
└── renderers/
    ├── __init__.py
    ├── latex_renderer.py    # Display math → PNG
    ├── inline_latex.py      # Inline $...$ → Unicode/HTML
    ├── code_renderer.py     # Syntax-highlighted code → PNG
    └── _image_utils.py      # Image utilities (rounded corners)
```

### `cli.py` — Command-Line Interface

- `main()` — Entry point: parses args (`-t`, `-c`, `-o`, `--open`, `--serve`), loads config, runs converter, writes HTML
- `_extract_images(html, images_dir)` — Replaces base64 `<img>` sources with extracted files (for serve mode)
- `_find_free_port()` — Finds available TCP port for local HTTP server
- `_get_ngrok_url(max_attempts)` — Polls ngrok local API for public tunnel URL
- `_serve(serve_dir, html_name)` — Starts local HTTP server + ngrok tunnel, opens browser

### `config.py` — Configuration

Dataclasses:
- `CodeConfig` — Code cell rendering settings (`font_size`, `theme`, `line_numbers`, `font`, `image_width`, `padding_x/y`, `separator`, `background`, `border_radius`)
- `LatexConfig` — Display math rendering settings (`font_size`, `dpi`, `color`, `background`, `padding`, `image_width`, `try_usetex`, `preamble`, `border_radius`)
- `Config` — Top-level aggregator (`image_width`, `border_radius`, `code: CodeConfig`, `latex: LatexConfig`)

Functions:
- `load_config(path)` — Loads YAML config; sub-configs inherit top-level `image_width`/`border_radius` unless overridden
- `apply_platform_defaults(config, platform)` — Applies platform-specific overrides (X/Medium get smaller widths and font sizes; Substack unchanged)

### `converter.py` — Conversion Orchestrator

Class `Converter`:
- `convert(notebook_path)` — Main pipeline: read notebook → collect preamble → collect equation labels → process cells → return concatenated HTML
- `_markdown_cell(cell)` — Protect code blocks → resolve `\eqref` → extract display math → render to PNG → convert inline math to Unicode → Markdown→HTML
- `_code_cell(cell, tags)` — Render source as syntax-highlighted PNG → process outputs (stream/text→PNG, image/svg/html→embed) → stack PNGs vertically → add footer
- `_output_as_png(output)` — Returns PNG bytes for text-based outputs, None for rich outputs
- `_render_output(output)` — Returns HTML for rich outputs (PNG as data-URI, inline SVG, inline HTML)

Module helpers:
- `_png_uri(png_bytes)` — Encodes PNG bytes as `data:image/png;base64,...`
- `_apply_eq_tag(latex, eq_labels)` — Strips `\label{...}`, returns (clean_latex, equation_number)
- `_cell_tags(cell)` — Extracts tags from cell metadata (`hide-cell`, `hide-input`, `hide-output`, `latex-preamble`)
- `_notebook_language(nb)` — Detects language from kernel metadata, defaults to "python"
- `_execute_cells(nb, cwd)` — Executes code cells via Jupyter kernel (for .qmd)

### `qmd_reader.py` — Quarto Parser

- `read_qmd(path)` — Parses `.qmd` → nbformat NotebookNode (split front matter, detect language, extract cells)
- `_split_front_matter(text)` — Extracts YAML front matter from document
- `_detect_language(fm, text)` — Detects language from front matter `engine`/`jupyter.kernel` or first code chunk
- `_extract_cells(text, default_lang)` — Parses body into notebook cells; handles `{output}`, `{latex-preamble}`, and regular code chunks
- `_parse_chunk(body)` — Translates `#|` options to tags (`echo: false`→`hide-input`, etc.), returns (tags, source)
- `_apply_option(opt, tags)` — Maps a single `#|` option string to cell tags

### Renderers (`nb2wb/renderers/`)

#### `latex_renderer.py` — Display Math → PNG

Two-tier strategy: tries full LaTeX+dvipng first, falls back to matplotlib mathtext.

- `extract_display_math(text)` — Finds all `$$...$$`, `\[...\]`, `\begin{equation}...` blocks; returns `(start, end, latex)` tuples
- `render_latex_block(latex, config, preamble, tag)` — Renders display math to data-URI PNG with fallback
- `_render_usetex(latex, config, preamble, tag)` — Full LaTeX→DVI→PNG pipeline via subprocess
- `_render_mathtext(latex, config, tag)` — Matplotlib mathtext fallback (no LaTeX needed)
- `_trim_and_pad(png_bytes, config, tag)` — Trims whitespace, pads, centers on fixed-width canvas, applies border radius
- `_draw_tag(canvas, tag, config)` — Draws equation number "(N)" at right edge
- `_color_to_html(color)` / `_color_to_dvipng(color)` — Color format conversions

#### `inline_latex.py` — Inline Math → Unicode

Converts `$...$` to Unicode via unicodeit, with superscript/subscript mapping and `<em>` for variables.

- `convert_inline_math(text)` — Replaces every `$...$` with Unicode/HTML equivalent
- `_to_unicode(latex)` — Pipeline: expand `\frac` → unicodeit → Unicode scripts → strip braces → italicize variables
- `_expand_frac(latex)` — `\frac{a}{b}` → `(a)/(b)`
- `_expand_scripts(text)` — `^{...}` / `_{...}` → Unicode superscripts/subscripts (or `<sup>`/`<sub>` fallback)
- `_script_html(inner, table, tag)` — Maps chars to Unicode script chars, falls back to HTML tag
- `_brace_arg(s, pos)` — Extracts content of `{...}` brace group
- `_italicize(text)` — Wraps single-letter variables and Greek letters in `<em>`

#### `code_renderer.py` — Syntax-Highlighted Code → PNG

PIL + Pygments rendering to PNG. Font fallback chain: DejaVu → Liberation → Ubuntu → FreeFont.

- `render_code(source, language, config)` — Tokenizes + paints syntax-highlighted code to PNG
- `render_output_text(text, config)` — Renders plain-text output in muted style to PNG
- `vstack_and_pad(png_list, config)` — Stacks PNGs vertically, normalizes widths, adds footer/border/padding
- `_paint(lines, font, style_cls, ...)` — Core renderer: draws tokenized lines onto PIL image with line numbers
- `_tokenize(source, language, style_cls)` — Pygments tokenization → per-line `[(rgb, text), ...]`
- `_load_font(size)` / `_find_font()` — Loads monospace font with platform-specific fallback
- `_outer_pad(png_bytes, ...)` — Wraps image with outer padding
- `_draw_footer(png_bytes, ...)` — Appends Jupyter-style footer bar (execution count, language)
- `_draw_border(png_bytes, ...)` — Draws thin border adapted to theme brightness
- `_create_output_style(base_style)` — Creates muted Pygments style for output cells
- `_text_w`, `_line_height`, `_hex_to_rgb`, `_shift`, `_default_fg`, `_rgb_to_hex` — Utilities for text measurement and color manipulation

#### `_image_utils.py`

- `round_corners(img, radius)` — Applies transparent rounded corners via alpha-channel mask

### Platform Builders (`nb2wb/platforms/`)

#### `base.py` — Abstract Base

Class `PlatformBuilder` (abstract):
- `name` (property, abstract) — Human-readable platform name
- `build_page(content_html)` (abstract) — Wraps content in complete HTML page
- `_to_data_uri(src)` — Converts image URL/path to base64 data-URI with security checks
- `_fetch_url_as_data_uri(url)` — Fetches remote image with SSRF/timeout/size/MIME validation
- `_read_file_as_data_uri(src)` — Reads local image with path-traversal protection
- `_make_images_copyable(html)` — Wraps `<img>` tags with per-image copy buttons

Module helper:
- `_is_private_host(hostname)` — SSRF protection: blocks private/loopback addresses

#### `substack.py` — `SubstackBuilder`

- `build_page(content_html)` — Embeds all images as base64, single "Copy to clipboard" button
- `_convert_external_images(html)` — Converts all external `<img>` sources to data-URIs

#### `medium.py` — `MediumBuilder`

- `build_page(content_html)` — Per-image hover "Copy image" buttons; supports `--serve` for public URLs

#### `x.py` — `XArticlesBuilder`

- `build_page(content_html)` — Per-image copy buttons; X strips embedded images so users copy manually

#### `__init__.py`

- `get_builder(platform)` — Returns platform builder instance by name
- `list_platforms()` — Returns list of supported platform names

## Test Markers

- `@pytest.mark.unit` — Isolated component tests
- `@pytest.mark.integration` — Component interaction tests
- `@pytest.mark.latex` — Requires LaTeX+dvipng installed
- `@pytest.mark.slow` — Long-running tests

### Test Structure

```
tests/
├── conftest.py                        # Shared fixtures & markers
├── unit/
│   ├── test_config.py                 # Config defaults, YAML loading, inheritance, platform defaults
│   ├── test_inline_latex.py           # $...$ → Unicode conversion, fractions, scripts, italicization
│   ├── test_latex_renderer.py         # Display math extraction, rendering, color conversion, equation numbering
│   ├── test_code_renderer.py          # Code/output rendering, image stacking, font/color/style handling
│   └── platforms/
│       └── test_image_security.py     # SSRF blocking, path traversal, MIME validation, size limits
├── integration/
│   └── test_converter_markdown.py     # Full markdown cell processing pipeline
└── workflow/
    └── test_cli.py                    # CLI arguments, end-to-end conversion
```

Key fixtures in `tests/conftest.py`: `default_config`, `minimal_config`, `x_platform_config`, `mock_latex_available`, `mock_latex_unavailable`, `mock_font_available`, programmatically-generated notebooks (`minimal_notebook`, `markdown_notebook`, `code_notebook`, `tagged_notebook`, `equation_numbered_notebook`, `latex_preamble_notebook`), and temp file helpers (`temp_notebook`, `temp_qmd`, `temp_config`).
