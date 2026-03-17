# For Maintainers

This page is the shortest accurate map of the current architecture. Use it when you need to change behavior without drifting away from the package boundaries that the tests enforce.

## Project Direction

`nb2wb` keeps three ideas stable:

1. `convert()` and `revert()` are content-only APIs.
2. Filesystem loading happens at explicit loader and CLI boundaries.
3. Safety checks and sanitization stay on in the default conversion path.

## Canonical Interfaces

### Public API

- `nb2wb.convert(notebook, ..., working_dir=None, raw_mode=False)`
- `nb2wb.revert(document, ..., ocr_pipeline=None)`
- `nb2wb.load_input_payload(path)`
- `nb2wb.load_html_payload(path)`
- typed loader helpers for notebook, Markdown, and Quarto sources

Accepted `convert()` payloads:

- notebook mapping or `NotebookNode`
- Markdown string
- Quarto string
- `{"format": "md", "content": "..."}`
- `{"format": "qmd", "content": "..."}`

Accepted `revert()` payloads:

- HTML string
- `{"format": "html", "content": "..."}`

### CLI Boundary

Forward CLI flow:

1. sanitize paths
2. `load_input_payload(path)`
3. `convert(payload, ...)`
4. write HTML

Reverse CLI flow:

1. sanitize paths
2. `load_html_payload(path)`
3. `revert(payload, ...)`
4. write notebook

### Converter Core

`nb2wb.converter.Converter.convert_notebook(notebook, cwd=...)` is the in-memory rendering entry point. Path handling does not belong in `Converter`.

## End-to-End Data Flow

### Forward Path

1. `nb2wb.api.convert(...)`
2. config resolution and target-option merge
3. payload coercion
4. notebook rendering through `Converter`
5. wrapper generation through `get_builder(...).build_page(...)`

### Reverse Path

1. `nb2wb.api.revert(...)`
2. HTML payload coercion
3. `Reverter.revert_html(...)`
4. optional OCR hook per image block
5. notebook scaffold assembly

## Module Map

| Module | Responsibility |
| --- | --- |
| `nb2wb/api.py` | public API, payload coercion, loader helpers, config resolution |
| `nb2wb/_notebook_payload.py` | notebook payload normalization and compatibility repair |
| `nb2wb/_path_utils.py` | shared path validation helpers |
| `nb2wb/cli.py` | forward CLI argument parsing, file I/O, `--serve` flow |
| `nb2wb/revert_cli.py` | reverse CLI argument parsing and OCR pipeline wiring |
| `nb2wb/config.py` | config dataclasses, YAML loading, target-profile defaults |
| `nb2wb/converter.py` | notebook-to-HTML fragment conversion |
| `nb2wb/reverter.py` | HTML-to-notebook scaffold conversion |
| `nb2wb/md_reader.py` | Markdown parsing into notebook cells |
| `nb2wb/qmd_reader.py` | Quarto parsing into notebook cells |
| `nb2wb/html_reader.py` | HTML payload loader with `source_dir` support |
| `nb2wb/_reader_utils.py` | shared front-matter and notebook-construction helpers |
| `nb2wb/sanitizer.py` | HTML and SVG sanitization |
| `nb2wb/platforms/base.py` | safe image handling and base wrapper logic |
| `nb2wb/platforms/builder.py` | profile-driven page builder and target option validation |
| `nb2wb/platforms/profiles.py` | declarative target profiles |

## Rendering Invariants

Inside `Converter`:

1. apply safety limits
2. optionally execute the notebook
3. render markdown cells
4. render code and outputs
5. sanitize rich HTML and SVG fragments
6. concatenate content fragments

Cells skipped from final output:

- raw notebook cells
- cells tagged `hide-cell`
- cells tagged `latex-preamble`

## Safety Invariants

Do not bypass these layers in normal flows:

- notebook size and workload limits
- HTML and SVG sanitization
- CSS URL filtering
- SSRF-safe remote image fetching
- local path traversal protection

If you need a different trust model, build it as an explicit alternative path. Do not silently weaken the default one.

## Current Legacy Surface

Legacy notebook support still exists because it is active product behavior, not dead code. It currently covers:

- older worksheet-style notebook payloads
- selected legacy code and output field names
- deterministic cell-id repair

Historical profile-specific builder shims are gone. The canonical wrapper entry point is `nb2wb.platforms.get_builder(...)`.

## Verification Workflow

Run these before you merge behavior changes:

```bash
pytest
sphinx-build -b html docs docs/_build/html
MPLCONFIGDIR=/tmp/matplotlib-cache python3 tests/perf/benchmark_runtime.py
```

Notes:

- the benchmark script is optional
- execution-related tests may warn in restricted environments, but the suite still checks graceful degradation

## Repository Landmarks

- `nb2wb/`: package code
- `nb2wb/renderers/`: rendering backends
- `nb2wb/platforms/`: wrapper profiles and image-safety helpers
- `docs/`: user and maintainer docs
- `examples/`: synchronized sample content
- `tests/`: unit, integration, workflow, and benchmark coverage
