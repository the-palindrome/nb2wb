# Reverse Conversion

`wb2nb` and `nb2wb.revert()` recover notebook structure from published HTML. This path is intentionally conservative: it gives you a scaffold that is easy to edit, not a byte-for-byte recreation of the original executed notebook.

## What Reverse Conversion Recovers Well

- article prose
- headings, lists, links, and basic inline formatting
- supported code blocks
- image references
- image-derived code, tables, or equations when OCR is enabled

## What It Leaves as a Scaffold

- unsupported code languages stay fenced in markdown
- ordinary figures stay linked images
- executed notebook outputs are not reconstructed from generic prose HTML
- OCR results may still need human cleanup

## Quick Start

Use the CLI when the source is an HTML file:

```bash
wb2nb article.html
wb2nb article.html -o recovered.ipynb
wb2nb examples/reverse_article.html
```

Use the Python API when the HTML is already in memory:

```python
import nb2wb

payload = nb2wb.load_html_payload("examples/reverse_article.html")
notebook = nb2wb.revert(payload)
```

## How the Reverse Path Decides What to Do

The reverse pipeline walks the document in order and classifies blocks:

- prose containers become markdown
- recognized `<pre><code>` blocks become code cells
- unsupported code blocks become fenced markdown
- images become markdown figures unless OCR says otherwise

The content root is chosen in this order:

1. `<article>`
2. `<main>`
3. `<body>`
4. the document root as a fallback

## Supported Code Languages

The built-in scaffold recognizes these languages as notebook code cells:

- `python`
- `r`
- `julia`
- `bash`
- `javascript`
- `typescript`
- `sql`

Unknown or unsupported languages are preserved as fenced markdown so the content does not disappear.

## OCR Is Optional

Reverse conversion skips OCR by default. That keeps the path fast, deterministic, and dependency-light when you only need prose plus code blocks.

Turn OCR on when your article contains:

- equation screenshots
- table screenshots
- code screenshots

Keep OCR off when the article mostly contains HTML prose and ordinary code blocks.

## Built-In OCR Pipelines

### Local OCR

Install:

```bash
pip install "nb2wb[ocr]"
```

The local stack uses Pix2Text for classification, tables, and LaTeX. It uses `pytesseract` plus the `tesseract` system binary for code screenshots.

### OpenAI OCR

Install:

```bash
pip install "nb2wb[openai]"
```

Use:

```python
from nb2wb.ocr.openai import OpenAIOCRPipeline

pipeline = OpenAIOCRPipeline(model="your-model-name")
```

Pass `allow_remote_image_urls=False` when you want the OpenAI-backed pipeline to leave public remote image URLs on the linked-figure fallback path instead of fetching and uploading them.

### Google Gemini OCR

Install:

```bash
pip install "nb2wb[gemini]"
```

Use:

```python
from nb2wb.ocr.gemini import GeminiOCRPipeline

pipeline = GeminiOCRPipeline(model="gemini-2.0-flash")
```

Pass `allow_remote_image_urls=False` when you want the Gemini-backed pipeline to leave public remote image URLs on the linked-figure fallback path instead of fetching and uploading them.

For CLI debugging, add `--verbose` to print package debug logs to stderr while `wb2nb` runs, including OCR progress and timing when OCR is enabled.

## Image Source Limits

The built-in OCR pipelines always read:

- local paths
- relative paths resolved from `source_dir`
- `data:` image URIs

The `local` OCR pipeline also reads public `http://` and `https://` image URLs.

The `openai` and `gemini` pipelines fetch public remote image URLs by default. Set `allow_remote_image_urls=False` in Python or use `wb2nb --disallow-remote-image-urls` in the CLI when you want those providers to leave remote images on the safe linked-figure path instead. Blocked attempts log a warning and keep the image linked.

Remote URL fetching remains SSRF-safe by default: private/loopback hosts are blocked, redirects are revalidated, payload size is capped, and the full transfer must finish within the timeout budget.

## Custom OCR Contract

Custom OCR keeps the reverse pipeline flexible without changing its core rules.

Input:

- one `OCRRequest` object with image context

Output:

```python
{"type": "latex" | "code" | "table" | "figure", "payload": "..."}
```

Interpretation:

- `figure`: keep the image linked
- `latex`: create a markdown math cell
- `table`: create a markdown cell
- `code`: create a code cell

## Reverse Metadata

The reverse path marks the notebook with:

```python
notebook.metadata["wb2nb"] = {
    "source_format": "html",
    "reverse_scaffold": 1,
}
```

OCR-derived cells also receive `metadata["wb2nb"]` with source and classification details. That metadata is useful when you want to review OCR results in a later cleanup pass.

## Example Workflow

Try the bundled example:

```bash
wb2nb examples/reverse_article.html -o examples/reverse_article.ipynb
python3 examples/revert_html_api.py
```

The example HTML includes:

- prose sections
- a recognized Python code block
- an unsupported Mermaid block that stays fenced in markdown
- a local image that stays linked unless OCR is enabled

## Related Pages

- [Input Formats](input-formats.md)
- [Python API](python-api.md)
- [CLI Reference](cli-reference.md)
- [Troubleshooting](troubleshooting.md)
