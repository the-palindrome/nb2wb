# nb2wb Documentation

`nb2wb` converts notebook-style writing into publishable HTML and can scaffold HTML posts back into notebooks when you need a starting point for revision or reuse.

Use this documentation when you want to publish from `.ipynb`, `.md`, or `.qmd`, integrate the converter into a backend service, or recover article content from HTML with optional OCR.

## Choose Your Path

- Start here if you want a fast first run: [Getting Started](getting-started.md)
- Browse the full rendering pipeline: [Feature Tour](feature-tour.md)
- Check every CLI flag: [CLI Reference](cli-reference.md)
- Integrate the package into a service: [Python API](python-api.md)
- Recover a notebook from HTML: [Reverse Conversion](reverse-conversion.md)
- Tune output and safety limits: [Configuration](configuration.md)
- Pick the right publishing wrapper: [Platforms](platforms.md)

```{toctree}
:maxdepth: 2
:caption: User Guide

getting-started
feature-tour
cli-reference
python-api
reverse-conversion
input-formats
configuration
platforms
security
server-integration
troubleshooting
```

```{toctree}
:maxdepth: 2
:caption: Maintainers

for-maintainers
development
```

## What `nb2wb` Covers

- Forward conversion from notebooks, Markdown, and Quarto.
- Optional notebook execution before rendering.
- Display math, code, stream output, rich HTML, SVG, and table handling.
- Target-specific wrappers for common publishing platforms.
- Reverse HTML-to-notebook scaffolding with optional OCR.
- Mandatory sanitization and workload limits for safer backend use.

## Examples

The repository ships synchronized examples in `examples/` for both forward and reverse workflows. Start with `examples/README.md` when you want sample content that matches the current docs.
