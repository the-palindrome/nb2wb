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
)
```

## `notebook` Input Types

`notebook` accepts:

- `str` or `pathlib.Path`
  - must point to `.ipynb`, `.qmd`, or `.md`
- `dict` (JSON/JSONB parsed notebook payload)
- `nbformat.NotebookNode`

In-memory notebook payloads are validated against nbformat schema before conversion.

## `config` Input Types

`config` accepts:

- `None` (defaults)
- `dict` with same schema as `config.yaml`
- `nb2wb.Config`
- YAML path (`str` or `Path`)

## Return Value

Returns one string: full HTML document for the selected target.

## `supported_targets()`

```python
import nb2wb

print(nb2wb.supported_targets())
# ['substack', 'x', 'medium']
```

## Path-Based Example

```python
import nb2wb

html = nb2wb.convert(
    "post.ipynb",
    config="config.yaml",
    target="substack",
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

## Execution Working Directory

For in-memory payloads with `execute=True`, set `working_dir` to control relative imports/paths during execution:

```python
html = nb2wb.convert(
    notebook_payload,
    execute=True,
    working_dir="/srv/notebook-jobs/job-123",
)
```

For path-based inputs, `working_dir` is ignored and notebook parent directory is used.

## Exceptions

Common failures raised by the API:

- `ValueError`
  - invalid notebook/config payload
  - unsupported path suffix
  - safety limit violations
- `FileNotFoundError`
  - missing input path or `working_dir`
- `TypeError`
  - unsupported object types for `notebook` or `config`

## Threading and Service Usage

`nb2wb.convert()` is stateless per call and suitable for request-scoped use in web services.

For high-throughput systems, consider process workers for isolation and controlled concurrency.
