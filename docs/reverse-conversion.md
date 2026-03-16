# Reverse Conversion

`wb2nb` and `nb2wb.revert()` convert HTML posts back into scaffolded Jupyter notebooks.
This workflow is best for recovering article structure, prose, code blocks, and image-derived content.
It does not recreate the original executed notebook state byte-for-byte.

## What Reverse Conversion Produces

The reverse pipeline walks the HTML document and rebuilds notebook cells with conservative rules:

- prose HTML becomes markdown cells
- recognized code blocks become notebook code cells
- unsupported or unknown code languages stay fenced in markdown
- images stay linked as markdown images unless you opt into OCR
- OCR can turn image content into markdown or code cells for `latex`, `table`, and `code` results

The built-in language scaffold currently recognizes:

- `python`
- `r`
- `julia`
- `bash`
- `javascript`
- `typescript`
- `sql`

## Quick Start

Use the CLI when your source is an HTML file:

```bash
wb2nb article.html
wb2nb article.html -o recovered.ipynb
wb2nb article.html --ocr-pipeline local
OPENAI_API_KEY=... wb2nb article.html --ocr-pipeline openai --model your-model-name
GEMINI_API_KEY=... wb2nb article.html --ocr-pipeline gemini --model gemini-2.0-flash
```

Use the Python API when the HTML already lives in memory:

```python
import nb2wb
from nb2wb.ocr.openai import OpenAIOCRPipeline
from nb2wb.ocr.gemini import GeminiOCRPipeline

payload = nb2wb.load_html_payload("article.html")
notebook = nb2wb.revert(payload)

# With OpenAI OCR
ocr_notebook = nb2wb.revert(
    payload,
    ocr_pipeline=OpenAIOCRPipeline(model="your-model-name", api_key="..."),
)

# With Gemini OCR
gemini_notebook = nb2wb.revert(
    payload,
    ocr_pipeline=GeminiOCRPipeline(model="gemini-2.0-flash", api_key="..."),
)
```

`nb2wb.revert()` is content-only.
Use `nb2wb.load_html_payload()` for filesystem HTML so relative image paths resolve through `source_dir`.

## OCR Is Optional

Reverse conversion skips OCR by default.
When you do not pass an OCR pipeline, the reverse path keeps images as linked markdown figures.

This default is deliberate.
It keeps reverse conversion fast and avoids model dependencies when you only need prose and preserved code blocks.

## Built-In OCR Pipelines

### Local OCR

Install the local OCR extra:

```bash
pip install nb2wb[ocr]
```

The local pipeline combines:

- Pix2Text for page classification, tables, and LaTeX
- `pytesseract` plus the `tesseract` system binary for code screenshots

If these dependencies are missing, or if classification/OCR fails, the reverse path falls back to the safe `figure` result and keeps the image linked in markdown.

### OpenAI OCR

Install the OpenAI extra:

```bash
pip install nb2wb[openai]
```

Then provide `OPENAI_API_KEY` and a model name:

```python
from nb2wb.ocr.openai import OpenAIOCRPipeline

pipeline = OpenAIOCRPipeline(model="your-model-name")
```

The OpenAI pipeline sends the image plus surrounding HTML context to the Responses API and expects structured JSON back.

### Google Gemini OCR

Install the Gemini extra:

```bash
pip install nb2wb[gemini]
```

Then provide `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) and a model name:

```python
from nb2wb.ocr.gemini import GeminiOCRPipeline

pipeline = GeminiOCRPipeline(model="gemini-2.0-flash")
```

The Gemini pipeline works the same way as the OpenAI pipeline: it sends the image and its surrounding HTML context to the Gemini API and returns structured classification results. You can pass an explicit `api_key` argument, or let the pipeline pick up the key from the `GEMINI_API_KEY` or `GOOGLE_API_KEY` environment variables.

## Important Image-Source Limitation

The built-in OCR pipelines only read:

- local file paths
- relative paths resolved from `source_dir`
- image `data:` URIs

They do not download remote `http://` or `https://` image URLs for OCR.
If your HTML references remote images, the built-in OCR pipelines fall back to `figure`, and the reverse notebook keeps those images as linked markdown figures.

If you need remote-image OCR, provide a custom `ocr_pipeline` that fetches or resolves those images in your own environment.

## Custom OCR Pipeline Contract

A custom OCR pipeline receives one `OCRRequest` object with context fields such as:

- `src`
- `alt`
- `title`
- `classes`
- `caption`
- `nearby_text`
- `source_dir`

It must return a mapping shaped like:

```python
{"type": "latex" | "code" | "table" | "figure", "payload": "..."}
```

Rules:

- `type="figure"` must use an empty string payload
- `type="latex"` becomes a markdown math cell
- `type="table"` becomes a markdown cell
- `type="code"` becomes a code cell

This keeps the reverse pipeline deterministic even when OCR behavior varies by backend.

## Notebook Metadata Added by the Reverse Path

The reverse scaffold marks the output notebook with:

```python
notebook.metadata["wb2nb"] = {
    "source_format": "html",
    "reverse_scaffold": 1,
}
```

When OCR turns an image into a notebook cell, that cell also gets `metadata["wb2nb"]` describing the image source and classification:

- `source_kind`
- `classification`
- `src`
- `alt`
- `ocr_type`

This metadata is useful when you want to review or post-process OCR-derived cells.

## What the Reverse Path Does Not Reconstruct

Reverse conversion intentionally produces a scaffold, not a perfect reconstruction.
Plan for manual cleanup in these cases:

- executed outputs are not reconstructed from ordinary prose HTML
- unsupported code languages remain fenced markdown instead of code cells
- OCR results are best-effort and may need editing
- figure images stay images unless OCR classifies them as notebook content

## Related Pages

- [Input Formats](input-formats.md)
- [CLI Reference](cli-reference.md)
- [Python API](python-api.md)
- [Troubleshooting](troubleshooting.md)
