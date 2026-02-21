# nb2wb

**Write in notebooks. Publish anywhere.**

`nb2wb` converts:

- Jupyter notebooks (`.ipynb`)
- Quarto documents (`.qmd`)
- Markdown files (`.md`)

into platform-ready HTML for:

- Substack
- Medium
- X Articles

The output is designed for copy/paste workflows where platforms often break MathJax and code formatting.

---

## Why `nb2wb`

Most publishing editors strip or mangle:

- LaTeX
- code blocks
- notebook outputs

`nb2wb` preserves fidelity by rendering complex parts as images and converting inline math to Unicode.

| Content type | Converted as |
|---|---|
| Inline math `$...$` | Unicode + light HTML formatting |
| Display math (`$$...$$`, `\[...\]`, `\begin{...}`) | PNG |
| Code input | Syntax-highlighted PNG (or copyable text snippet) |
| Text outputs / errors | PNG |
| `image/png` outputs | Embedded as image data URI |
| `image/svg+xml` outputs | Sanitized SVG as image data URI |
| `text/html` outputs | Sanitized HTML fragment |

---

## Feature Overview

- Converts `.ipynb`, `.qmd`, and `.md` from one CLI.
- Platform-specific page wrappers for Substack, Medium, and X.
- One-click copy toolbar in generated HTML.
- Medium/X per-image copy buttons for reliable image transfer.
- Optional `--serve` mode (local server + ngrok URL).
- Equation labels and cross-references:
  - `\label{...}` in display math
  - `\eqref{...}` replaced with `(N)`
- LaTeX rendering strategy:
  - tries full `latex + dvipng`
  - falls back to matplotlib mathtext
- Inline LaTeX conversion pipeline:
  - unicode command replacement
  - superscript/subscript expansion
  - variable italicization
- Code rendering controls:
  - Pygments theme
  - line numbers
  - font size
  - padding / border radius
- Cell-level visibility and behavior tags:
  - `hide-cell`, `hide-input`, `hide-output`, `latex-preamble`, `text-snippet`
- Markdown directives in `.md` via `<!-- nb2wb: ... -->`.
- Quarto `#|` options mapped to notebook-style tags.
- Security hardening for image fetching and HTML/SVG embedding.

---

## Installation

```bash
pip install nb2wb
```

Development install:

```bash
git clone https://github.com/the-palindrome/nb2wb.git
cd nb2wb
pip install -e ".[dev]"
```

---

## Quick Start

```bash
nb2wb notebook.ipynb
nb2wb notebook.ipynb -t medium
nb2wb notebook.ipynb -t x
nb2wb notebook.ipynb -o article.html
nb2wb notebook.ipynb --open
nb2wb notebook.ipynb --serve
nb2wb article.md
nb2wb article.md --execute
nb2wb report.qmd
```

Default output path is `<input_basename>.html`.

---

## CLI Reference

```text
nb2wb <input.{ipynb|qmd|md}> [options]
```

| Option | Meaning |
|---|---|
| `-t, --target {substack,medium,x}` | Target platform (`substack` default) |
| `-c, --config PATH` | YAML config file |
| `-o, --output PATH` | Output HTML path |
| `--open` | Open generated HTML in browser |
| `--serve` | Extract images, start local server, expose via ngrok |
| `--execute` | Execute code cells before rendering (`.ipynb`, `.qmd`, `.md`) |

---

## Platform Behavior

| Platform | Paste workflow | Image behavior |
|---|---|---|
| Substack | One-click copy/paste | Embedded images transfer directly |
| Medium | Copy/paste + optional per-image copy | Base64 images may be stripped by editor |
| X Articles | Copy/paste + optional per-image copy | Base64 images may be stripped by editor |

### `--serve` mode

`--serve` helps Medium/X workflows by replacing embedded data URIs with public HTTP URLs.

What it does:

1. Extracts supported image MIME types from the generated HTML into `images/`
2. Rewrites `<img src="...">` to those files
3. Starts local HTTP server
4. Starts ngrok tunnel and opens the public URL

Requirements:

- `ngrok` installed
- `ngrok` authenticated (`ngrok config add-authtoken <TOKEN>`)

---

## Input Format Support

### `.ipynb`

- Uses notebook cells and outputs directly.
- Supports notebook tags in `cell.metadata.tags`.
- Uses notebook/kernel metadata to infer language for syntax highlighting.

Execution:

- Not executed by default
- Executed when `--execute` is provided

### `.md`

Supported features:

- Optional YAML front matter
- Fenced code blocks with backticks or tildes
- Per-fence tags (` ```python hide-input ` style)
- Directive comments:
  - `<!-- nb2wb: hide-input -->`
  - `<!-- nb2wb: hide-output -->`
  - `<!-- nb2wb: hide-cell -->`
  - `<!-- nb2wb: text-snippet -->`
  - comma-separated combinations are supported
- Special fence language:
  - `latex-preamble`

Execution:

- Not executed by default
- Executed when `--execute` is provided

### `.qmd`

Supported features:

- Optional YAML front matter
- Quarto fenced chunks (` ```{python} ` etc.)
- Quarto options mapped to tags:
  - `#| echo: false` -> `hide-input`
  - `#| output: false` -> `hide-output`
  - `#| include: false` or `#| eval: false` -> `hide-cell`
  - `#| tags: [tag1, tag2]` -> tags
- Special chunk languages:
  - `latex-preamble`
  - `output` (attaches stdout to the immediately preceding code cell)

Execution:

- Not executed by default
- Executed when `--execute` is provided

---

## Cell Tags

| Tag | Effect |
|---|---|
| `hide-cell` | Hide entire cell (input + output) |
| `hide-input` | Hide code input |
| `hide-output` | Hide outputs |
| `latex-preamble` | Use cell/chunk content as LaTeX preamble and hide it |
| `text-snippet` | Render code as `<pre><code>` instead of PNG |

`hide-cell` applies to markdown cells too.

---

## LaTeX Features

### Display math

Detected forms include:

- `$$...$$`
- `\[...\]`
- `\begin{equation}...\end{equation}`
- `\begin{align}...\end{align}`
- `\begin{gather}...\end{gather}`
- `\begin{multline}...\end{multline}`
- `\begin{eqnarray}...\end{eqnarray}`
- starred variants where applicable

### Equation numbering and references

- `\label{eq:name}` assigns equation number
- `\eqref{eq:name}` is replaced with `(N)` across the document

### Inline math

Inline `$...$` expressions are converted to Unicode-oriented text with script handling.

---

## LaTeX Preamble Sources

All of these are combined:

1. Config (`latex.preamble`)
2. Notebook markdown cells tagged `latex-preamble`
3. `.md` fenced blocks labeled `latex-preamble`
4. `.qmd` chunks `{latex-preamble}`

Note:

- preamble only affects full LaTeX (`try_usetex: true` path)
- matplotlib mathtext fallback ignores custom preamble

---

## Output Rendering Details

For code cells:

- Source code -> syntax-highlighted PNG
- Footer includes execution count and language label
- Text output / tracebacks -> muted output PNG block

Rich outputs:

- `image/png` -> embedded directly
- `image/svg+xml` -> sanitized and embedded as `data:image/svg+xml;base64,...`
- `text/html` -> sanitized HTML fragment

Raw notebook cells are skipped.

---

## Configuration

Pass with:

```bash
nb2wb notebook.ipynb -c config.yaml
```

### Complete config schema (with defaults)

```yaml
# Global defaults
image_width: 1920
border_radius: 14

code:
  font_size: 48
  theme: "monokai"
  line_numbers: true
  font: "DejaVu Sans Mono"
  image_width: 1920
  padding_x: 100
  padding_y: 100
  separator: 0
  background: ""       # empty = use theme background
  border_radius: 14

latex:
  font_size: 48
  dpi: 150
  color: "black"
  background: "white"
  padding: 68          # pixels
  image_width: 1920
  try_usetex: true
  preamble: ""
  border_radius: 0
```

Inheritance behavior:

- `code.image_width` and `latex.image_width` inherit top-level `image_width` unless overridden
- `code.border_radius` and `latex.border_radius` inherit top-level `border_radius` unless overridden

### Platform defaults applied automatically

When target is `medium` or `x`, defaults are adjusted for narrower layouts:

- top-level `image_width`: `680`
- `code.font_size`: `42`
- `code.image_width`: `1200`
- `code.padding_x`: `30`
- `code.padding_y`: `30`
- `code.separator`: `0`
- `latex.font_size`: `35`
- `latex.padding`: `50`
- `latex.image_width`: `1200`

Substack keeps base defaults unless your config overrides them.

### Code themes

Any Pygments style works. Example:

```bash
python -c "from pygments.styles import get_all_styles; print(sorted(get_all_styles()))"
```

---

## Security Model

`nb2wb` includes guardrails for image ingestion and HTML embedding:

### Image URL/file safety

- Only `http` / `https` remote image URLs are allowed
- Requests to private/loopback hosts are blocked (SSRF protection)
- Redirect targets are re-validated (no public-to-private redirect bypass)
- Download timeout and max size checks are enforced
- MIME type allowlist is enforced for fetched/read images
- Local image paths:
  - absolute paths rejected
  - `..` traversal rejected
  - symlink escape outside current working directory rejected

### Embedded content sanitization

- Markdown-generated HTML is sanitized before embedding
- `text/html` outputs are sanitized
- SVG outputs are sanitized, then embedded via image data URI
- Dangerous tags/attributes/URI schemes are stripped or neutralized

### CLI input sanitization

- Input path is validated to be one of: `.ipynb`, `.qmd`, `.md`
- CLI paths containing control characters are rejected

Important:

- Notebook execution via `--execute` runs code. Treat untrusted notebooks as untrusted code.
- LaTeX rendering is independent of `--execute`; the external `latex`/`dvipng` path is sanitized and run with `-no-shell-escape`.
- Sanitization is best-effort, not a browser sandbox.

---

## Requirements

Core dependencies:

- Python `>=3.9`
- `nbformat`
- `nbconvert`
- `ipykernel`
- `matplotlib`
- `Pillow`
- `Pygments`
- `PyYAML`
- `markdown`
- `unicodeit`

Optional system tools:

- LaTeX + `dvipng` (for highest-fidelity display math rendering)
- `ngrok` (for `--serve`)

---

## Development

Run tests:

```bash
pytest
pytest tests/unit/
pytest tests/integration/
pytest tests/workflow/
```

Format:

```bash
black nb2wb tests
isort nb2wb tests
```

---

## Limitations

- Platforms can change paste behavior without notice.
- Medium/X may still require per-image copy depending editor behavior.
- Extremely complex custom HTML can be altered by sanitization.
- Execution with `--execute` requires a working Jupyter kernel setup.

---

## License

MIT
