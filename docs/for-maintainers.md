# For Maintainers

This page is a technical overview of the project for maintainers and coding agents.

## Purpose and Scope

`nb2wb` converts notebook-style inputs into platform-ready HTML for Substack, Medium, and X.

Current architectural direction:

- keep `nb2wb.api.convert()` content-only
- keep filesystem loading explicit via helper functions
- keep conversion logic centralized in a single in-memory notebook pipeline
- keep safety checks mandatory in normal execution paths

## Canonical Interfaces (Do Not Drift)

### Public API

- `nb2wb.convert(notebook, ..., working_dir=None)` accepts in-memory payloads only.
- `nb2wb.load_input_payload(path)` and typed helpers are responsible for filesystem reads.
- `notebook` input forms accepted by `convert`:
  - notebook dict / `NotebookNode`
  - markdown or quarto text string
  - mapping payloads such as `{"format": "md", "content": "..."}`

### Converter Core

- `nb2wb.converter.Converter` converts in-memory notebook models through:
  - `Converter.convert_notebook(notebook, cwd=...)`
- Path-based conversion is intentionally not part of `Converter`.

### CLI

- CLI remains path-based at the command boundary.
- CLI path flow is:
  1. sanitize input/output/config paths
  2. `load_input_payload(path)`
  3. `convert(payload, ...)`
  4. write resulting HTML

## End-to-End Data Flow

### API path

1. `nb2wb.api.convert(...)`
2. `_resolve_config(...)` + `apply_platform_defaults(...)`
3. payload normalization (`_coerce_api_payload`)
4. `Converter.convert_notebook(...)`
5. platform wrapper `builder.build_page(...)`

### `.md`/`.qmd` path

1. loader helper reads file text
2. API parses text using `read_md_text(...)` / `read_qmd_text(...)`
3. parsed notebook proceeds through the same converter path as `.ipynb`

### Rendering path (inside `Converter`)

1. safety limits on serialized notebook + cell/output bounds
2. optional execution via `nbconvert.ExecutePreprocessor`
3. markdown cells:
  - protect code spans
  - render display math blocks to PNG
  - convert inline math
  - optional table-to-image replacement
  - sanitize resulting HTML
4. code cells:
  - render input/output text to images
  - sanitize rich HTML/SVG output fragments
5. concatenate fragments

## Security and Safety Layers

- Notebook-level limits: `nb2wb/converter.py` (`_enforce_serialized_notebook_size`, `_enforce_notebook_limits`)
- HTML/SVG sanitization: `nb2wb/sanitizer.py`
- Platform image safety for external/local sources:
  - SSRF and private-host rejection
  - path traversal rejection
  - MIME allowlist + byte-size caps
  - implemented in `nb2wb/platforms/base.py`

## Module Map

| Module | Responsibility |
|---|---|
| `nb2wb/api.py` | Public programmatic interface, payload coercion, config resolution, loader helpers |
| `nb2wb/cli.py` | CLI argument parsing, path validation, file I/O, optional `--serve` flow |
| `nb2wb/config.py` | Dataclass config schema, YAML/dict loading, platform defaults |
| `nb2wb/converter.py` | Core in-memory notebook-to-fragment conversion |
| `nb2wb/md_reader.py` | Markdown text/file to notebook model |
| `nb2wb/qmd_reader.py` | Quarto text/file to notebook model |
| `nb2wb/_reader_utils.py` | Shared reader utilities (front matter + notebook construction) |
| `nb2wb/sanitizer.py` | Safe HTML/SVG sanitization profiles |
| `nb2wb/renderers/code_renderer.py` | Code/output text image rendering |
| `nb2wb/renderers/latex_renderer.py` | Display-math extraction and image rendering |
| `nb2wb/renderers/inline_latex.py` | Inline LaTeX to unicode/text conversions |
| `nb2wb/renderers/table_renderer.py` | HTML table-to-image rendering |
| `nb2wb/renderers/_image_utils.py` | Shared image post-processing helpers |
| `nb2wb/platforms/base.py` | Shared platform wrapper helpers + safe image conversion |
| `nb2wb/platforms/substack.py` | Substack page wrapper |
| `nb2wb/platforms/medium.py` | Medium page wrapper |
| `nb2wb/platforms/x.py` | X Articles page wrapper |
| `tests/unit/` | Fast unit tests per module and security components |
| `tests/integration/` | Cross-module conversion behavior tests |
| `tests/workflow/` | CLI behavior and end-to-end workflow tests |

## Repository Layout (Tracked Files)

The list below reflects tracked files in git (excluding generated build/cache artifacts).

```text
.
├── .github/
│   └── workflows/
│       └── publish.yml
├── .gitignore
├── .readthedocs.yaml
├── LICENSE
├── README.md
├── docs/
│   ├── cli-reference.md
│   ├── conf.py
│   ├── configuration.md
│   ├── development.md
│   ├── feature-tour.md
│   ├── for-maintainers.md
│   ├── getting-started.md
│   ├── index.md
│   ├── input-formats.md
│   ├── platforms.md
│   ├── python-api.md
│   ├── security.md
│   ├── server-integration.md
│   └── troubleshooting.md
├── examples/
│   ├── README.md
│   ├── config.yaml
│   ├── image.png
│   ├── markdown.md
│   ├── notebook.html
│   ├── notebook.ipynb
│   ├── quarto.html
│   ├── quarto.qmd
│   └── x_article.ipynb
├── nb2wb/
│   ├── __init__.py
│   ├── __main__.py
│   ├── _reader_utils.py
│   ├── api.py
│   ├── cli.py
│   ├── config.py
│   ├── converter.py
│   ├── md_reader.py
│   ├── platforms/
│   │   ├── __init__.py
│   │   ├── _templates.py
│   │   ├── base.py
│   │   ├── medium.py
│   │   ├── substack.py
│   │   └── x.py
│   ├── qmd_reader.py
│   ├── renderers/
│   │   ├── __init__.py
│   │   ├── _image_utils.py
│   │   ├── code_renderer.py
│   │   ├── inline_latex.py
│   │   ├── latex_renderer.py
│   │   └── table_renderer.py
│   └── sanitizer.py
├── pyproject.toml
├── requirements.txt
└── tests/
    ├── README.md
    ├── __init__.py
    ├── conftest.py
    ├── integration/
    │   ├── __init__.py
    │   ├── test_converter_markdown.py
    │   └── test_converter_md.py
    ├── unit/
    │   ├── __init__.py
    │   ├── platforms/
    │   │   ├── __init__.py
    │   │   └── test_image_security.py
    │   ├── test_api.py
    │   ├── test_code_renderer.py
    │   ├── test_config.py
    │   ├── test_inline_latex.py
    │   ├── test_latex_renderer.py
    │   ├── test_md_reader.py
    │   ├── test_sanitizer.py
    │   └── test_table_renderer.py
    └── workflow/
        ├── __init__.py
        └── test_cli.py
```

## Maintainer Checklist for Changes

When changing the codebase, verify these invariants:

1. `nb2wb.api.convert()` remains content-only.
2. Path input is handled only by loader helpers and CLI path boundary code.
3. Converter entrypoint remains `convert_notebook(...)` for in-memory models.
4. Safety checks and sanitization are not bypassed in default flows.
5. Unit + integration + workflow tests remain green.
