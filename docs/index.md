# nb2wb Documentation

`nb2wb` converts notebooks and notebook-like documents into platform-ready HTML for copy/paste publishing.

Use this documentation for end-to-end usage: local CLI runs, Python API integration, server-side deployment, and security hardening.

```{toctree}
:maxdepth: 2
:caption: User Guide

feature-tour
getting-started
cli-reference
python-api
input-formats
configuration
platforms
security
server-integration
troubleshooting
development
```

## What nb2wb Does

- Converts `.ipynb`, `.qmd`, and `.md` into full HTML pages.
- Preserves math and code fidelity by rendering display math and code blocks as images.
- Supports Substack, Medium, and X Articles output wrappers.
- Provides a Python API (`nb2wb.convert`) for backend integration.
- Applies mandatory server-safe sanitization and notebook resource limits.

## Quick Links

- Project README: `README.md`
- Python API entrypoint: `nb2wb/api.py`
- Conversion pipeline: `nb2wb/converter.py`
- Security sanitizer: `nb2wb/sanitizer.py`
