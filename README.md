# nb2wb

**Write in notebooks. Publish anywhere.**

`nb2wb` converts Jupyter Notebooks and other notebook-style content into publishable HTML for Substack, Medium, X Articles, LinkedIn, Dev.to, Hashnode, Ghost, and WordPress.

Supported inputs:

- Jupyter notebooks (`.ipynb`)
- Quarto documents (`.qmd`)
- Markdown documents (`.md`)
- in-memory Jupyter notebook payloads (`dict` / `NotebookNode`)

## Documentation

- Detailed docs (Read the Docs): `https://nb2wb.readthedocs.io/`
- Docs source in this repo: `docs/index.md`

## Brief Feature Tour

1. **Load notebook content** from file or in-memory payload.
2. **Optionally execute code cells** (`--execute` / `execute=True`).
3. **Render markdown, math, code, and outputs** into platform-safe HTML fragments.
4. **Convert display math, code, and (optionally) tables to images** for high-fidelity publishing.
5. **Sanitize rich HTML/SVG output** and enforce server-side safety limits.
6. **Wrap output for your target platform** (`substack`, `medium`, `x`, `linkedin`, `devto`, `hashnode`, `ghost`, `wordpress`).

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

## Quick Start (CLI)

```bash
nb2wb notebook.ipynb
nb2wb notebook.ipynb -t medium
nb2wb notebook.ipynb -t x
nb2wb notebook.ipynb -t linkedin
nb2wb notebook.ipynb -t devto
nb2wb notebook.ipynb -o article.html
nb2wb notebook.ipynb --open
nb2wb notebook.ipynb --serve
nb2wb notebook.ipynb --raw -o article_raw.html
nb2wb report.qmd --execute
nb2wb report.ipynb -t ghost --image-strategy embed --article-width 900
```

## Quick Start (Python API)

```python
import nb2wb

# Path input via loader helper
payload = nb2wb.load_input_payload("notebook.ipynb")
html = nb2wb.convert(
    payload,
    target="substack",
    config={"latex": {"try_usetex": True}},
)

# In-memory payload input (JSON / JSONB parsed notebook)
html = nb2wb.convert(
    notebook_payload,
    target="substack",
    execute=False,
)

# Raw-mode output (no <head>, toolbar, or JavaScript)
html = nb2wb.convert(
    notebook_payload,
    target="medium",
    raw_mode=True,
)

# Override target features at call-time
html = nb2wb.convert(
    notebook_payload,
    target="devto",
    target_options={
        "image_strategy": "copyable",
        "copy_script_mode": "copyable",
        "article_width_px": 780,
    },
)
```

`nb2wb.convert()` is content-only; use `load_input_payload()` (or typed loaders) for filesystem inputs.

## Security at a Glance

`nb2wb` uses a mandatory server-safe conversion pipeline:

- strict HTML/SVG sanitization
- CSS URL sanitization
- SSRF-safe image fetching
- path traversal protection for local files
- notebook size/resource safety limits
- fail-closed behavior for unsafe/unresolvable image sources

Important: enabling execution runs notebook code. Treat `execute=True` workloads as untrusted code and isolate them appropriately.

## Configuration

Use YAML file in CLI:

```bash
nb2wb notebook.ipynb -c config.yaml
```

Or pass dict/object/path in API:

```python
html = nb2wb.convert(notebook_payload, config={"safety": {"max_cells": 1500}})
```

## Read More

- [Feature Tour](docs/feature-tour.md)
- [Getting Started](docs/getting-started.md)
- [CLI Reference](docs/cli-reference.md)
- [Python API](docs/python-api.md)
- [Input Formats](docs/input-formats.md)
- [Configuration](docs/configuration.md)
- [Platforms](docs/platforms.md)
- [Security Model](docs/security.md)
- [FastAPI/API Integration](docs/server-integration.md)
- [Troubleshooting](docs/troubleshooting.md)
- [For Maintainers](docs/for-maintainers.md)

## Development

Run tests:

```bash
pytest
```

Build docs locally:

```bash
pip install -e ".[docs]"
sphinx-build -b html docs docs/_build/html
```

## License

MIT
