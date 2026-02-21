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
| Code input | Syntax-highlighted PNG (or text snippet mode) |
| Stream/error output | PNG image |
| `image/png` output | Embedded directly |
| `image/svg+xml` output | Sanitized, then embedded as data URI |
| `text/html` output | Sanitized HTML fragment |

## 3. Platform Wrapping

After cell conversion, content is wrapped for one of:

- `substack`
- `medium`
- `x`

Each wrapper provides copy/paste-friendly layout and controls.

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
