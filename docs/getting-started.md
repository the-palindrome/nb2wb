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
The same command shape also works for `.md` and `.qmd` inputs.

Common variants:

```bash
nb2wb notebook.ipynb -t medium
nb2wb notebook.ipynb -t x
nb2wb notebook.ipynb -t linkedin
nb2wb notebook.ipynb -t devto
nb2wb notebook.ipynb -o article.html
nb2wb notebook.ipynb --open
nb2wb notebook.ipynb --raw -o article_raw.html
nb2wb notebook.ipynb -t ghost --image-strategy embed --article-width 900
```

## First Conversion (Python API)

```python
import nb2wb

payload = nb2wb.load_input_payload("notebook.ipynb")
html = nb2wb.convert(
    payload,
)
```

`nb2wb.convert()` accepts in-memory payloads; use loader helpers for path-based sources.
`nb2wb.convert(Path("notebook.ipynb"))` is rejected on purpose, and a plain
string such as `"notebook.ipynb"` is parsed as Markdown text rather than loaded
from disk.

In-memory notebook payload:

```python
import nb2wb

html = nb2wb.convert(notebook_payload_dict)
```

Raw mode from API:

```python
import nb2wb

html = nb2wb.convert(notebook_payload_dict, target="medium", raw_mode=True)
```

In raw mode, output omits `<head>`, toolbar/header controls, and JavaScript.

## Local Serve Mode (for copyable-image workflows)

```bash
nb2wb notebook.ipynb --serve
```

This extracts image data URIs into an `images/` directory next to the output
HTML, rewrites the page to use those relative files, starts a local HTTP
server, and exposes the served page through ngrok.

If you pass both `--serve` and `--open`, the serve flow wins and opens the
tunneled page.

Requirements:

- `ngrok` installed
- `ngrok config add-authtoken <TOKEN>` completed

## Next Steps

- [CLI Reference](cli-reference.md)
- [Python API](python-api.md)
- [Server Integration](server-integration.md)
