# Python API

Use the Python API when integrating `nb2wb` into backend services.

## Main Entry Point

```python
import nb2wb

html = nb2wb.convert(
    notebook,
    config=None,
    target="default",
    target_options=None,
    execute=False,
    working_dir=None,
    raw_mode=False,
)
```

## Parameter Reference

| Parameter | Type | Meaning |
|---|---|---|
| `notebook` | `str \| Mapping \| nbformat.NotebookNode` | In-memory source payload (never a path object) |
| `config` | `None \| dict-like \| Config \| str \| Path` | Config object, mapping, or YAML path |
| `target` | `str` | Target wrapper: `default`, `substack`, `medium`, `x`, `linkedin`, `devto`, `hashnode`, `ghost`, `wordpress` |
| `target_options` | `Mapping \| None` | Optional profile feature overrides (`image_strategy`, `raw_image_strategy`, `copy_script_mode`, `article_width_px`, `table_mode`, `toolbar_message`, `theme_overrides`) |
| `execute` | `bool` | Execute code cells before rendering |
| `working_dir` | `str \| Path \| None` | Execution working directory when `execute=True` |
| `raw_mode` | `bool` | Strip wrapper chrome (`<head>`, toolbar, JS) |

## Input Formats (Detailed)

### 1. Notebook Object Payloads

Accepted:

- `nbformat.NotebookNode`
- notebook `dict`/mapping (for example from JSON/JSONB)

Required notebook fields after normalization/validation include:

- `nbformat`
- `nbformat_minor`
- `cells`
- `metadata`

Behavior:

- payload is normalized and validated via `nbformat`
- payloads are canonicalized to internal `nbformat=4`, `nbformat_minor=5`
- legacy major versions (for example v3 `worksheets` payloads) are upgraded to v4
- conservative legacy repairs are applied for known lossless patterns:
  - `code.input` -> `code.source` (when `source` missing)
  - `prompt_number` -> `execution_count` (when missing)
  - stream outputs `stream` -> `name` (when missing)
  - output aliases `pyout` -> `execute_result`, `pyerr` -> `error`
- missing or duplicate/invalid cell ids are repaired deterministically
- missing `kernelspec.display_name` is derived from `kernelspec.name` when available
- unsupported major versions and unknown non-legacy schema fields fail with actionable `ValueError`

### 2. In-Memory Text Payloads

Accepted as plain `str`:

- Markdown text
- Quarto text (auto-detected when Quarto chunk fences are present, such as ```` ```{python} ````)
- path-like strings are still treated as text content (for example `"post.ipynb"` is parsed as markdown text, not loaded from disk)

Accepted as explicit mapping payload:

- `{"format": "md", "content": "<markdown text>"}`
- `{"format": "qmd", "content": "<quarto text>"}`

Format aliases:

- `markdown` -> `md`
- `quarto` -> `qmd`

Content key aliases:

- `content` (preferred)
- `source`
- `text`

### 3. Path Loader Helper Output Contracts

`nb2wb.convert()` is content-only and does not accept paths directly.
Use loader helpers for filesystem inputs:

| Helper | Input | Output payload |
|---|---|---|
| `nb2wb.load_input_payload(path)` | `.ipynb`, `.md`, `.qmd` | notebook node (`.ipynb`) or text mapping (`.md`/`.qmd`) |
| `nb2wb.load_notebook_payload(path)` | `.ipynb` | validated `NotebookNode` |
| `nb2wb.load_markdown_payload(path)` | `.md` | `{"format": "md", "content": "..."}` |
| `nb2wb.load_quarto_payload(path)` | `.qmd` | `{"format": "qmd", "content": "..."}` |

Use loader helpers whenever your source is a filesystem path.

## Output Formats (Detailed)

`nb2wb.convert()` always returns a single `str` containing an HTML document.
Both modes include a `<!DOCTYPE html>` root and a `<body>` containing:

- a content container: `<div id="content">...</div>`
- converted notebook cell output (markdown/code/output fragments)

### Normal Mode (`raw_mode=False`)

Normal mode includes the full preview wrapper:

- `<head>...</head>` with CSS and metadata
- toolbar/header with copy controls
- JavaScript block for copy interactions

Target-specific image wrapping (defaults):

- `copyable`: `medium`, `x`, `linkedin` (image container + copy button)
- `embed`: `default`, `substack`, `devto`, `hashnode`, `ghost`, `wordpress`

Typical structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>...</head>
<body>
  <div id="toolbar">...</div>
  <div id="content">...</div>
  <script>...</script>
</body>
</html>
```

### Raw Mode (`raw_mode=True`)

Raw mode strips all preview chrome:

- removes `<head>...</head>`
- removes toolbar/header controls
- removes all JavaScript (`<script>` blocks)

Target-specific image behavior in raw mode follows each target profile's
`raw_image_strategy` (default: embed for all built-in targets).

Typical structure:

```html
<!DOCTYPE html>
<html lang="en">
<body>
  <div id="content">...</div>
</body>
</html>
```

## Output Contract for Automation

Recommended stable assumptions for agent/tool integrations:

- return type is always one HTML `str`
- output includes `<!DOCTYPE html>` and an `<html ...>` root
- converted article content is wrapped under `#content`
- `raw_mode=False` includes `<head>`, toolbar controls, and a `<script>` block
- `raw_mode=True` excludes `<head>`, toolbar controls, and all `<script>` blocks

Details you should treat as unstable implementation details:

- exact CSS content and variable names
- exact toolbar message text
- JavaScript function names/implementation
- incidental wrapper class names outside explicitly documented mode-level behavior

## `config` Input Types

`config` accepts:

- `None` (defaults)
- `dict` with same schema as `config.yaml`
- `nb2wb.Config`
- YAML path (`str` or `Path`)

## `supported_targets()`

```python
import nb2wb

print(nb2wb.supported_targets())
# ['default', 'substack', 'medium', 'x', 'linkedin', 'devto', 'hashnode', 'ghost', 'wordpress']
```

## `target_options` Example

```python
import nb2wb

html = nb2wb.convert(
    notebook_payload,
    target="devto",
    target_options={
        "image_strategy": "copyable",
        "raw_image_strategy": "preserve",
        "copy_script_mode": "copyable",
        "article_width_px": 780,
        "table_mode": "native",
    },
)
```

## Path-Based Example

```python
import nb2wb

payload = nb2wb.load_input_payload("post.ipynb")
html = nb2wb.convert(
    payload,
    config="config.yaml",
    target="substack",
    working_dir=".",  # optional; useful with execute=True
)
```

## In-Memory Notebook Example

```python
import nb2wb

html = nb2wb.convert(
    notebook_payload,   # dict from API body / JSONB
    config={
        "latex": {"try_usetex": True},
        "safety": {
            "max_cells": 1500,
            "max_input_bytes": 20 * 1024 * 1024,
        },
    },
    target="substack",
    execute=False,
)
```

## In-Memory Markdown / Quarto Examples

```python
import nb2wb

# Raw markdown string payload
md_html = nb2wb.convert(
    "# Title\n\nBody text.",
    target="substack",
)

# Raw qmd string payload
qmd_html = nb2wb.convert(
    "# Report\n\n```{python}\nprint('hello')\n```",
    target="medium",
)

# Explicit mapping payload (recommended when format is ambiguous)
md_html2 = nb2wb.convert(
    {"format": "md", "content": "One-line markdown without newline"},
    target="substack",
)
```

## Raw Mode Example

```python
import nb2wb

html = nb2wb.convert(
    notebook_payload,
    target="medium",
    raw_mode=True,
)
```

## Execution Working Directory

For in-memory payloads with `execute=True`, set `working_dir` to control relative imports/paths during execution:

```python
html = nb2wb.convert(
    notebook_payload,
    execute=True,
    working_dir="/srv/notebook-jobs/job-123",
)
```

## Exceptions

Common failures raised by the API:

- `ValueError`
  - invalid notebook/config payload
  - safety limit violations
- `FileNotFoundError`
  - missing loader input path or `working_dir`
- `TypeError`
  - unsupported object types for `notebook` or `config`

## Threading and Service Usage

`nb2wb.convert()` is stateless per call and suitable for request-scoped use in web services.

For high-throughput systems, consider process workers for isolation and controlled concurrency.
