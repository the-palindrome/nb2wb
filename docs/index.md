# nb2wb Documentation

`nb2wb` converts Jupyter Notebooks and notebook-like documents into platform-ready HTML for copy/paste publishing.

Use this documentation for end-to-end usage: local CLI runs, Python API integration, forward notebook-to-HTML conversion, reverse HTML-to-notebook scaffolding, server-side deployment, and security hardening.

```{toctree}
:maxdepth: 2
:caption: User Guide

feature-tour
getting-started
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

## What nb2wb Does

- Converts `.ipynb`, `.qmd`, and `.md` into full HTML pages.
- Converts `.html` and `.htm` back into scaffolded notebooks through `wb2nb` and `nb2wb.revert()`.
- Preserves math and code fidelity by rendering display math and code blocks as images.
- Supports Substack, Medium, X Articles, LinkedIn, Dev.to, Hashnode, Ghost, and WordPress output wrappers.
- Provides Python APIs for both conversion (`nb2wb.convert`) and reverse scaffolding (`nb2wb.revert`).
- Applies mandatory server-safe sanitization and notebook resource limits.

## Quick Links

- Project README: `README.md`
- Python API entrypoint: `nb2wb/api.py`
- Conversion pipeline: `nb2wb/converter.py`
- Security sanitizer: `nb2wb/sanitizer.py`
- Maintainer overview: `docs/for-maintainers.md`
