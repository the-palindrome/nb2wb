# Feature Tour

This page is a practical tour of what happens from input document to publishable HTML.

## 1. Supported Inputs

`nb2wb` accepts:

- Jupyter notebooks (`.ipynb`)
- Quarto documents (`.qmd`)
- Markdown documents (`.md`)

All inputs are normalized into a notebook-like model and then rendered by the same pipeline.

## 2. Rendered Output Types

| Notebook content | Output behavior |
|---|---|
| Inline math (`$...$`) | Unicode-oriented inline rendering |
| Display math (`$$...$$`, `\[...\]`, `\begin{...}`) | PNG image |
| Code input | Syntax-highlighted PNG, or `<pre><code>` when tagged `text-snippet` |
| Stream/error output | PNG image |
| `image/png` output | Embedded directly |
| `image/svg+xml` output | Sanitized, then embedded as data URI |
| `text/html` output | Sanitized HTML fragment |
| Markdown/HTML tables | Native HTML table or PNG image, depending on config and target |

## 3. Platform Wrapping

After cell conversion, content is wrapped for one of:

- `default`
- `substack`
- `medium`
- `x`
- `linkedin`
- `devto`
- `hashnode`
- `ghost`
- `wordpress`

Each wrapper provides copy/paste-friendly layout and controls unless raw mode
is enabled. Built-in profiles default to `embed` or `copyable` image
strategies, and API/config overrides can also use `preserve`.

## 4. Equation Labels and References

Across markdown cells, `nb2wb` tracks equation labels and references:

- `\label{eq:name}` assigns equation numbers.
- `\eqref{eq:name}` is replaced with `(N)`.

## 5. Optional Execution

Code execution is disabled by default.

- CLI: add `--execute`
- Python API: pass `execute=True`

When enabled, notebooks are executed through Jupyter kernels before rendering.

## 6. Server-Safe by Default

The conversion pipeline always applies safety controls:

- HTML/SVG sanitization
- CSS URL sanitization
- SSRF-guarded image fetching
- Input and notebook resource limits
- Fail-closed image handling

For details, see [Security](security.md).

## 7. Cell-Level Visibility Rules

- Cells tagged `hide-cell` are omitted from final output.
- `latex-preamble` cells are hidden from output but still extend the LaTeX preamble.
- Raw notebook cells are skipped.

## 8. Reverse Conversion and OCR

`nb2wb` also supports the opposite direction through `wb2nb` and `nb2wb.revert()`.
This reverse path rebuilds prose and recognized code blocks as notebook cells and keeps ordinary images linked in markdown unless you opt into OCR.

When OCR is enabled:

- image equations can become markdown math cells
- image tables can become markdown table cells
- code screenshots can become code cells
- failed or unsupported OCR falls back to linked figures

For workflow details and OCR limitations, see [Reverse Conversion](reverse-conversion.md).
