# nb2wb Test Suite

This directory contains the automated verification surface for `nb2wb`.
The suite is organized by intent so maintainers can run a fast subset while
they iterate, then fall back to a single full `pytest` run before merging.

## Layout

The repository currently uses four test areas:

- `tests/unit/`: isolated coverage for API coercion, config loading, readers, renderers, sanitizer behavior, and platform image-safety helpers.
- `tests/integration/`: cross-module pipeline checks for markdown conversion, execution wiring, and safety-limit enforcement.
- `tests/workflow/`: CLI behavior, path validation, raw mode, target options, and legacy notebook compatibility.
- `tests/perf/benchmark_runtime.py`: manual runtime benchmark scenarios. This script is not part of the default pytest run.

Shared fixtures and test helpers live in `tests/conftest.py`.

## Current Modules

| Path | Focus |
|---|---|
| `tests/unit/test_api.py` | Public API, input coercion, loader helpers, targets, raw mode, and legacy notebook normalization |
| `tests/unit/test_code_renderer.py` | Code/output PNG rendering, tokenization, colors, layout, and font fallback behavior |
| `tests/unit/test_config.py` | Config loading, inheritance, and target-profile defaults |
| `tests/unit/test_inline_latex.py` | Inline LaTeX to Unicode/text conversion |
| `tests/unit/test_latex_renderer.py` | Display-math extraction, usetex validation, mathtext fallback, caching, and image post-processing |
| `tests/unit/test_md_reader.py` | Markdown parsing, directives, fence tags, language detection, and front matter |
| `tests/unit/test_sanitizer.py` | HTML/SVG sanitization and CSS URI restrictions |
| `tests/unit/test_table_renderer.py` | Table-to-image replacement |
| `tests/unit/platforms/test_image_security.py` | SSRF defenses, path traversal blocking, MIME checks, strict image handling, and `--serve` extraction helpers |
| `tests/integration/test_converter_markdown.py` | Markdown cell pipeline, equation references, and sanitization |
| `tests/integration/test_converter_md.py` | Markdown/Quarto execution wiring, text snippets, file conversion, and safety limits |
| `tests/workflow/test_cli.py` | CLI UX, output generation, execution flags, target options, serve/raw behavior, and compatibility regressions |

## Running the Suite

Run the full suite from the repository root:

```bash
pytest
```

If you use the checked-in virtual environment, you can run:

```bash
.venv/bin/python -m pytest
```

Targeted runs:

```bash
pytest tests/unit/
pytest tests/integration/
pytest tests/workflow/
pytest tests/unit/platforms/test_image_security.py
pytest -m "not latex"
```

Coverage run:

```bash
pytest --cov=nb2wb --cov-report=term --cov-report=html
```

## Markers

Pytest markers are defined in `pyproject.toml`:

- `unit`
- `integration`
- `latex`
- `slow`

Examples:

```bash
pytest -m unit
pytest -m integration
pytest -m "not latex"
pytest -m "not slow"
```

## Benchmarks

Use the benchmark script to watch runtime regressions in rendering-heavy paths:

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache python3 tests/perf/benchmark_runtime.py
```

The benchmark reports timings for:

- `code_heavy`
- `markdown_tiny`
- `math_repeated`

## Environment Notes

- The suite uses a non-interactive matplotlib backend through shared fixtures.
- Tests that exercise `--execute` may emit warnings in restricted CI or sandboxed environments when Jupyter kernel subprocesses are blocked. Those cases should still verify graceful degradation instead of hard failure.
- Some LaTeX renderer tests cover the fallback path, so the full suite does not require a complete system LaTeX installation to pass.

## Adding or Updating Tests

Keep new tests close to the behavior they verify:

1. Add isolated logic checks under `tests/unit/`.
2. Add cross-module conversion checks under `tests/integration/`.
3. Add CLI and end-to-end contract checks under `tests/workflow/`.
4. Reuse fixtures from `tests/conftest.py` instead of rebuilding notebook/config scaffolding in each file.
5. Run the narrowest relevant subset first, then run full `pytest` before merging.
