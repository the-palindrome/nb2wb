# For Maintainers

This page is a technical overview of the project for maintainers and coding agents.

## Purpose and Scope

`nb2wb` converts notebook-style inputs into platform-ready HTML for target profiles (`default`, `substack`, `medium`, `x`, `linkedin`, `devto`, `hashnode`, `ghost`, `wordpress`).

Current architectural direction:

- keep `nb2wb.api.convert()` content-only
- keep filesystem loading explicit via helper functions
- keep conversion logic centralized in a single in-memory notebook pipeline
- keep safety checks mandatory in normal execution paths

## Canonical Interfaces (Do Not Drift)

### Public API

- `nb2wb.convert(notebook, ..., working_dir=None, raw_mode=False)` accepts in-memory payloads only.
- `nb2wb.load_input_payload(path)` and typed helpers are responsible for filesystem reads.
- `.md` and `.qmd` loader helpers intentionally return text payload mappings
  instead of parsed notebooks.
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
2. `_resolve_config(...)` + `resolve_target_options(...)` + `apply_target_profile_defaults(...)`
3. payload normalization (`_coerce_api_payload`)
4. `Converter.convert_notebook(...)`
5. platform wrapper `builder.build_page(...)`

Notes:

- Passing a `Path` object to `convert()` is a type error by design.
- Passing a path-like string to `convert()` is still treated as text content.

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
  - honor `text-snippet` by emitting escaped `<pre><code>` instead of a PNG
  - sanitize rich HTML/SVG output fragments
5. concatenate fragments

Cells skipped from final output:

- raw notebook cells
- cells tagged `hide-cell`
- cells tagged `latex-preamble`

## Security and Safety Layers

- Notebook-level limits: `nb2wb/converter.py` (`_enforce_serialized_notebook_size`, `_enforce_notebook_limits`)
- HTML/SVG sanitization: `nb2wb/sanitizer.py`
- Platform image safety for external/local sources:
  - SSRF and private-host rejection
  - path traversal rejection
  - MIME allowlist + byte-size caps
  - fail-closed image dropping in `embed` and `copyable` modes
  - implemented in `nb2wb/platforms/base.py`

## Module Map

| Module | Responsibility |
|---|---|
| `nb2wb/api.py` | Public programmatic interface, payload coercion, config resolution, loader helpers |
| `nb2wb/cli.py` | CLI argument parsing, path validation, file I/O, optional `--serve` flow |
| `nb2wb/config.py` | Dataclass config schema, YAML/dict loading, target profile defaults |
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
| `nb2wb/platforms/profiles.py` | Declarative target profiles (theme/image/render defaults) |
| `nb2wb/platforms/builder.py` | Generic profile-driven page builder + target options |
| `tests/unit/` | Fast unit tests per module and security components |
| `tests/integration/` | Cross-module conversion behavior tests |
| `tests/workflow/` | CLI behavior and end-to-end workflow tests |

## Verification Workflow

Run these checks before you merge behavior changes:

```bash
pytest
sphinx-build -b html docs docs/_build/html
MPLCONFIGDIR=/tmp/matplotlib-cache python3 tests/perf/benchmark_runtime.py
```

Notes:

- The benchmark script is optional and measures runtime regressions outside the default test run.
- Execution-related tests may emit warnings in restricted environments where kernel subprocesses are blocked. The suite still verifies that conversion degrades gracefully.

## Test Surface

The automated checks are split by intent:

- `tests/unit/`: API coercion, config loading, readers, renderers, sanitizer behavior, and image security helpers.
- `tests/integration/`: markdown conversion pipeline, execution flag wiring, and safety-limit enforcement.
- `tests/workflow/`: CLI argument handling, output generation, raw mode, target options, and legacy notebook compatibility.
- `tests/perf/benchmark_runtime.py`: ad hoc benchmark scenarios for runtime tracking.

The detailed test guide lives in `tests/README.md`.

## Repository Landmarks

Prefer these directories as stable landmarks instead of maintaining an exhaustive file tree:

- `nb2wb/`: public API, CLI, readers, config, converter, sanitizer, and package exports.
- `nb2wb/renderers/`: code, LaTeX, inline-math, and table rendering backends.
- `nb2wb/platforms/`: wrapper templates, builder logic, target profiles, and shared image-safety helpers.
- `docs/`: Sphinx user and maintainer documentation.
- `examples/`: synchronized sample inputs and config for manual smoke tests.
- `tests/`: unit, integration, workflow, and benchmark coverage.
- `.github/workflows/` and `.readthedocs.yaml`: CI/release and docs build configuration.

## Maintainer Checklist for Changes

When changing the codebase, verify these invariants:

1. `nb2wb.api.convert()` remains content-only.
2. Path input is handled only by loader helpers and CLI path boundary code.
3. Converter entrypoint remains `convert_notebook(...)` for in-memory models.
4. Safety checks and sanitization are not bypassed in default flows.
5. Unit + integration + workflow tests remain green.
6. `build_page(..., raw_mode=True)` still returns a full HTML shell, just without head, toolbar, or scripts.
