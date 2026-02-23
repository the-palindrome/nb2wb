# Python API

Use the Python API when integrating `nb2wb` into backend services.

## Main Entry Point

```python
import nb2wb

html = nb2wb.convert(
    notebook,
    config=None,
    target="substack",
    execute=False,
    working_dir=None,
    raw_mode=False,
)
```

## `notebook` Input Types

`notebook` accepts:

- `str` (in-memory Markdown or Quarto text)
- `dict` (JSON/JSONB parsed notebook payload)
- `nbformat.NotebookNode`
- in-memory text payload mapping:
  - `{"format": "md", "content": "<markdown text>"}`
  - `{"format": "qmd", "content": "<quarto text>"}`
  - aliases: `format="markdown"` and `format="quarto"`
  - `source` or `text` can be used instead of `content`

In-memory notebook payloads are validated against nbformat schema before conversion.
In-memory `.md` / `.qmd` payloads use the same readers as file-based input.

`nb2wb.convert()` is strict content-only. It does not accept paths.
All string values are treated as content payloads (including path-like strings).

## Path Loader Helpers

Use helpers when your source is on disk:

- `nb2wb.load_input_payload(path)`:
  - `.ipynb` -> validated `NotebookNode`
  - `.md` -> `{"format": "md", "content": "..."}`
  - `.qmd` -> `{"format": "qmd", "content": "..."}`
- `nb2wb.load_notebook_payload(path)` (`.ipynb` only)
- `nb2wb.load_markdown_payload(path)` (`.md` only)
- `nb2wb.load_quarto_payload(path)` (`.qmd` only)

## `config` Input Types

`config` accepts:

- `None` (defaults)
- `dict` with same schema as `config.yaml`
- `nb2wb.Config`
- YAML path (`str` or `Path`)

## Return Value

Returns one string: full HTML document for the selected target.

## Raw Mode

Set `raw_mode=True` to emit a stripped-down HTML wrapper:

- removes `<head>...</head>`
- removes toolbar/header copy controls
- removes all JavaScript (`<script>` blocks)
- for `medium` and `x`, emits standard `<img ...>` tags (no `.image-container` wrappers)

```python
import nb2wb

html = nb2wb.convert(
    notebook_payload,
    target="medium",
    raw_mode=True,
)
```

## `supported_targets()`

```python
import nb2wb

print(nb2wb.supported_targets())
# ['substack', 'x', 'medium']
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

## In-Memory Example (API payload)

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
