# nb2wb

Write in notebooks. Publish anywhere.

`nb2wb` turns notebook-native writing into paste-ready HTML for editors that do not understand Jupyter, Quarto, or LaTeX. Start from a notebook, a Markdown article, or a Quarto document, then target a neutral preview wrapper or a profile tuned for Substack, Medium, X Articles, LinkedIn, Dev.to, Hashnode, Ghost, or WordPress.

The project also ships a reverse scaffold. Use `wb2nb` or `nb2wb.revert()` to turn published HTML back into a Jupyter notebook when you need to recover prose, code blocks, and image-derived content.

## Why People Reach for `nb2wb`

- Render code cells as syntax-highlighted images so theme and spacing survive copy and paste.
- Render display math as images and inline math as readable Unicode text.
- Keep tables as native HTML or convert them to images when a platform editor is unreliable.
- Wrap output for different publishing targets without rewriting article content.
- Serve extracted images through `--serve` when editors reject embedded data URIs.
- Reverse HTML posts back into notebook scaffolds, with OCR as an opt-in upgrade.
- Apply safety limits and HTML/SVG sanitization by default for server-side use.

## Supported Inputs

- Jupyter notebooks: `.ipynb`
- Quarto documents: `.qmd`
- Markdown documents: `.md`
- In-memory notebook payloads: `dict` / `nbformat.NotebookNode`
- In-memory text payloads: raw strings or `{"format": "...", "content": "..."}`
- Reverse conversion inputs: `.html`, `.htm`, and in-memory HTML payloads

## Installation

Install the base package:

```bash
pip install nb2wb
```

Install extras only when you need them:

```bash
pip install "nb2wb[ocr]"     # local OCR for reverse conversion
pip install "nb2wb[openai]"  # OpenAI-backed OCR pipeline
pip install "nb2wb[gemini]"  # Google Gemini-backed OCR pipeline
```

For development:

```bash
git clone https://github.com/the-palindrome/nb2wb.git
cd nb2wb
pip install -e ".[dev]"
```

## Quick Start

Convert a notebook to the default preview wrapper:

```bash
nb2wb notebook.ipynb
```

Target a platform profile:

```bash
nb2wb notebook.ipynb -t medium
nb2wb notebook.ipynb -t x
nb2wb notebook.ipynb -t linkedin
```

Use execution, raw mode, and wrapper overrides when you need them:

```bash
nb2wb report.qmd --execute
nb2wb report.ipynb --warnings
nb2wb report.ipynb --raw -o article_raw.html
nb2wb report.ipynb -t ghost --image-strategy embed --article-width 900
nb2wb report.ipynb --serve
nb2wb report.ipynb --verbose
```

Reverse an HTML article back into a notebook scaffold:

```bash
wb2nb article.html
wb2nb article.html -o recovered.ipynb
wb2nb article.html --ocr-pipeline local
OPENAI_API_KEY=... wb2nb article.html --ocr-pipeline openai --model your-model-name
OPENAI_API_KEY=... wb2nb article.html --ocr-pipeline openai --model your-model-name --disallow-remote-image-urls
GEMINI_API_KEY=... wb2nb article.html --ocr-pipeline gemini --model gemini-2.0-flash
GEMINI_API_KEY=... wb2nb article.html --ocr-pipeline gemini --model gemini-2.0-flash --disallow-remote-image-urls
GEMINI_API_KEY=... wb2nb article.html --ocr-pipeline gemini --model gemini-2.5-flash --verbose
```

`OpenAIOCRPipeline` and `GeminiOCRPipeline` allow public remote `http/https` image fetching by default. Pass `allow_remote_image_urls=False` in Python or `--disallow-remote-image-urls` in the CLI when you want those providers to leave remote images on the linked-figure fallback path.

## Python API

`nb2wb.convert()` is content-only. Load files with helpers first, then pass the in-memory payload into the converter.

```python
import nb2wb

payload = nb2wb.load_input_payload("notebook.ipynb")
html = nb2wb.convert(
    payload,
    target="substack",
    config={"latex": {"try_usetex": True}},
    verbose=True,
)
```

You can also enable package logging explicitly:

```python
import nb2wb

nb2wb.configure_logging(verbose=True)
```

You can also pass text or notebook payloads directly:

```python
import nb2wb

html = nb2wb.convert(
    {
        "format": "md",
        "content": "# Shipping Notes\n\n`nb2wb` handles this in memory.",
    },
    target="medium",
    raw_mode=True,
)
```

Reverse conversion follows the same pattern:

```python
import nb2wb

payload = nb2wb.load_html_payload("article.html")
notebook = nb2wb.revert(payload)
```

Add OCR only when you want image-derived notebook cells:

```python
from nb2wb.ocr.openai import OpenAIOCRPipeline

ocr_notebook = nb2wb.revert(
    payload,
    ocr_pipeline=OpenAIOCRPipeline(model="your-model-name"),
)
```

## Examples

The [`examples/`](examples/README.md) directory now covers forward conversion, reverse conversion, API usage, Markdown directives, Quarto `{output}` chunks, visibility tags, rich HTML/SVG outputs, and target-specific publishing flows.

Useful entry points:

- [`examples/notebook.ipynb`](examples/notebook.ipynb)
- [`examples/markdown.md`](examples/markdown.md)
- [`examples/quarto.qmd`](examples/quarto.qmd)
- [`examples/reverse_article.html`](examples/reverse_article.html)
- [`examples/convert_notebook_api.py`](examples/convert_notebook_api.py)
- [`examples/revert_html_api.py`](examples/revert_html_api.py)

## Security Model

`nb2wb` keeps the safe path on by default:

- HTML and SVG fragments are sanitized.
- CSS URLs are filtered.
- Remote image fetching is SSRF-safe.
- Local image handling blocks traversal and escape paths.
- Notebook payloads are constrained by configurable size and workload limits.

Execution is different. If you enable `--execute` or `execute=True`, treat the notebook as untrusted code and isolate that runtime yourself.

## Documentation

- Read the full docs: `https://nb2wb.readthedocs.io/`
- Start in the repo: [`docs/index.md`](docs/index.md)
- Follow the quick path: [`docs/getting-started.md`](docs/getting-started.md)
- Explore all features: [`docs/feature-tour.md`](docs/feature-tour.md)
- Integrate the API: [`docs/python-api.md`](docs/python-api.md)
- Recover notebooks from HTML: [`docs/reverse-conversion.md`](docs/reverse-conversion.md)

## Development

Run the test suite:

```bash
pytest
```

Build docs locally:

```bash
pip install -e ".[docs]"
sphinx-build -b html docs docs/_build/html
```

The detailed test guide lives in [`tests/README.md`](tests/README.md).

## License

MIT
