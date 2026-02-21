# Getting Started

## Install

```bash
pip install nb2wb
```

For development:

```bash
git clone https://github.com/the-palindrome/nb2wb.git
cd nb2wb
pip install -e ".[dev]"
```

## First Conversion (CLI)

```bash
nb2wb notebook.ipynb
```

This writes `notebook.html` by default.

Common variants:

```bash
nb2wb notebook.ipynb -t medium
nb2wb notebook.ipynb -t x
nb2wb notebook.ipynb -o article.html
nb2wb notebook.ipynb --open
```

## First Conversion (Python API)

```python
import nb2wb

html = nb2wb.convert(
    "notebook.ipynb",
    target="substack",
)
```

In-memory notebook payload:

```python
import nb2wb

html = nb2wb.convert(notebook_payload_dict, target="substack")
```

## Local Serve Mode (for Medium/X workflows)

```bash
nb2wb notebook.ipynb --serve
```

This extracts images, runs a local HTTP server, and creates an ngrok URL.

Requirements:

- `ngrok` installed
- `ngrok config add-authtoken <TOKEN>` completed

## Next Steps

- [CLI Reference](cli-reference.md)
- [Python API](python-api.md)
- [Server Integration](server-integration.md)
