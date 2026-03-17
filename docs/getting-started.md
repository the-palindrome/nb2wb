# Getting Started

This page gets you from install to a realistic first conversion as quickly as possible. Use the example files in `examples/` if you want a guided smoke test instead of starting from your own content.

## Install

Install the base package:

```bash
pip install nb2wb
```

Install extras only when the workflow needs them:

```bash
pip install "nb2wb[ocr]"     # local OCR for reverse conversion
pip install "nb2wb[openai]"  # OpenAI-backed OCR
pip install "nb2wb[gemini]"  # Google Gemini-backed OCR
```

The local OCR path also needs the `tesseract` system binary on `PATH` for code-image OCR.

For development:

```bash
git clone https://github.com/the-palindrome/nb2wb.git
cd nb2wb
pip install -e ".[dev]"
```

## First Forward Conversion

Convert a notebook, Markdown article, or Quarto document with the same command shape:

```bash
nb2wb notebook.ipynb
nb2wb examples/markdown.md
nb2wb examples/quarto.qmd
```

`nb2wb` writes `<input>.html` by default. The default target is a neutral preview wrapper that is useful when you want to inspect output before choosing a publishing destination.

Common variants:

```bash
nb2wb notebook.ipynb -t medium
nb2wb notebook.ipynb -t x
nb2wb notebook.ipynb -t linkedin
nb2wb notebook.ipynb --open
nb2wb notebook.ipynb --raw -o article_raw.html
nb2wb examples/markdown.md --execute --warnings
nb2wb notebook.ipynb --serve
```

Use `--execute` when the source does not already contain outputs. Add `--warnings` when you want `stderr` streams to appear in the rendered article.

## First Reverse Conversion

Use `wb2nb` when the source is an HTML article:

```bash
wb2nb article.html
wb2nb article.html -o recovered.ipynb
wb2nb examples/reverse_article.html
```

Reverse conversion keeps images linked by default. Add OCR only when you want screenshots or equations to become notebook cells:

```bash
wb2nb article.html --ocr-pipeline local
OPENAI_API_KEY=... wb2nb article.html --ocr-pipeline openai --model your-model-name
GEMINI_API_KEY=... wb2nb article.html --ocr-pipeline gemini --model gemini-2.0-flash
```

## First Python API Call

`nb2wb.convert()` accepts in-memory payloads, not paths. Load files first, then convert:

```python
import nb2wb

payload = nb2wb.load_input_payload("examples/notebook.ipynb")
html = nb2wb.convert(
    payload,
    target="substack",
    config={"table": {"mode": "image"}},
)
```

You can keep everything in memory for service integration:

```python
import nb2wb

html = nb2wb.convert(
    {
        "format": "md",
        "content": "# Shipping Notes\n\nThis article never touches the filesystem.",
    },
    raw_mode=True,
)
```

Reverse conversion follows the same pattern:

```python
import nb2wb

payload = nb2wb.load_html_payload("examples/reverse_article.html")
notebook = nb2wb.revert(payload)
```

## Try the Example Set

The example directory is meant to be read and executed, not just skimmed.

Suggested order:

1. `nb2wb examples/markdown.md --execute --warnings`
2. `nb2wb examples/quarto.qmd`
3. `python3 examples/convert_notebook_api.py`
4. `wb2nb examples/reverse_article.html`
5. `python3 examples/revert_html_api.py`

## What to Read Next

- [Feature Tour](feature-tour.md)
- [CLI Reference](cli-reference.md)
- [Python API](python-api.md)
- [Reverse Conversion](reverse-conversion.md)
- The `examples/` directory in the repository
