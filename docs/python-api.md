# Python API

Use the Python API when the content already lives in memory or when you want the converter inside a backend service, worker, or notebook-processing pipeline.

## `convert()`

```python
import nb2wb

html = nb2wb.convert(
    notebook,
    config=None,
    target="default",
    target_options=None,
    execute=False,
    warnings_mode=False,
    working_dir=None,
    raw_mode=False,
    verbose=False,
)
```

### Parameters

| Parameter | Type | Meaning |
| --- | --- | --- |
| `notebook` | `str | Mapping | nbformat.NotebookNode` | In-memory notebook or text payload |
| `config` | `None | Mapping | Config | str | Path` | Config object, mapping, or YAML path |
| `target` | `str` | Target profile name |
| `target_options` | `Mapping | TargetPageOptions | None` | Wrapper overrides |
| `execute` | `bool` | Execute code cells before rendering |
| `warnings_mode` | `bool` | Include `stderr` stream output |
| `working_dir` | `str | Path | None` | Execution working directory |
| `raw_mode` | `bool` | Remove preview chrome from output |
| `verbose` | `bool` | Emit package debug logs during this call |

`convert()` always returns one HTML string.

## Use Loader Helpers for Paths

`convert()` is content-only by design. Use loader helpers when the source starts as a path:

```python
import nb2wb

payload = nb2wb.load_input_payload("examples/notebook.ipynb")
html = nb2wb.convert(payload, target="substack")
```

Typed loaders are available when you want stricter input handling:

- `load_notebook_payload()`
- `load_markdown_payload()`
- `load_quarto_payload()`

Path behavior to remember:

- `nb2wb.convert("post.ipynb")` treats the string as document text
- `nb2wb.convert(Path("post.ipynb"))` raises `TypeError`
- `nb2wb.convert(nb2wb.load_input_payload("post.ipynb"))` loads and converts the file

## Accepted Input Shapes

### Notebook Payloads

Accepted forms:

- `nbformat.NotebookNode`
- notebook `dict` or mapping

Notebook payloads are normalized before rendering. That normalization includes:

- canonical internal target `nbformat=4`, `nbformat_minor=5`
- conservative upgrades from legacy worksheet payloads
- repairs for older code/output field names
- deterministic cell-id repair when ids are missing, invalid, or duplicated

Successful compatibility repairs emit a `RuntimeWarning`.

### Text Payloads

Accepted forms:

- raw Markdown string
- raw Quarto string
- `{"format": "md", "content": "..."}`
- `{"format": "qmd", "content": "..."}`

Format aliases:

- `markdown`
- `quarto`

Content aliases:

- `content`
- `source`
- `text`

Raw strings are auto-detected as Quarto only when Quarto chunk fences are present.

## Common Forward-Conversion Patterns

### Convert a File Through the Loader Boundary

```python
import nb2wb

payload = nb2wb.load_input_payload("examples/markdown.md")
html = nb2wb.convert(
    payload,
    target="medium",
    execute=True,
    warnings_mode=True,
)
```

### Convert a Notebook Payload From a Database

```python
import nb2wb

html = nb2wb.convert(
    notebook_payload,
    target="linkedin",
    target_options={
        "article_width_px": 760,
        "copy_script_mode": "copyable",
    },
)
```

### Emit Raw Article HTML

```python
import nb2wb

html = nb2wb.convert(
    notebook_payload,
    target="x",
    raw_mode=True,
)
```

## `revert()`

```python
import nb2wb

notebook = nb2wb.revert(
    document,
    ocr_pipeline=None,
    verbose=False,
)
```

### Parameters

| Parameter | Type | Meaning |
| --- | --- | --- |
| `document` | `str | Mapping[str, Any]` | In-memory HTML payload |
| `ocr_pipeline` | `Callable | None` | Optional OCR callable |
| `verbose` | `bool` | Emit package debug logs during this call |

`revert()` returns an `nbformat.NotebookNode`.

## Reverse-Conversion Inputs

Accepted forms:

- raw HTML string
- `{"format": "html", "content": "..."}`
- `{"format": "html", "content": "...", "source_dir": "..."}` via `load_html_payload()`

Use `load_html_payload()` when the HTML references local assets:

```python
import nb2wb

payload = nb2wb.load_html_payload("examples/reverse_article.html")
notebook = nb2wb.revert(payload)
```

`source_dir` matters because built-in OCR pipelines can resolve relative image paths from it.

## Logging

`nb2wb` uses Python's standard `logging` module with package loggers under `nb2wb.*`.

Enable verbose logging for one API call:

```python
import nb2wb

html = nb2wb.convert(payload, verbose=True)
notebook = nb2wb.revert(document, verbose=True)
```

Or configure package logging explicitly for a longer-lived process:

```python
import nb2wb

nb2wb.configure_logging(verbose=True)
```

## OCR Pipelines

OCR is optional. When `ocr_pipeline` is `None`, reverse conversion skips image transcription and keeps images linked in markdown.

Built-in options:

- `nb2wb.ocr.local.local_ocr_pipeline`
- `nb2wb.ocr.openai.OpenAIOCRPipeline`
- `nb2wb.ocr.gemini.GeminiOCRPipeline`

The built-in OCR pipelines always read:

- local file paths
- relative paths resolved from `source_dir`
- `data:` image URIs

The local OCR pipeline also reads public `http://` and `https://` image URLs.

The OpenAI and Gemini OCR pipelines fetch public remote `http://` and `https://` image URLs.

Remote URL fetching remains SSRF-safe by default: private/loopback hosts are rejected, redirects are revalidated, payload size is capped, and the full transfer must finish within the timeout budget.

### Custom OCR Contract

The OCR pipeline receives one `OCRRequest` object with fields such as:

- `src`
- `alt`
- `title`
- `classes`
- `caption`
- `nearby_text`
- `source_dir`

It must return:

```python
{"type": "latex" | "code" | "table" | "figure", "payload": "..."}
```

Rules:

- `figure` must use an empty payload
- `latex` becomes a markdown math cell
- `table` becomes a markdown cell
- `code` becomes a code cell

## Reverse Result Metadata

The reverse scaffold marks the notebook with:

```python
notebook.metadata["wb2nb"] = {
    "source_format": "html",
    "reverse_scaffold": 1,
}
```

OCR-derived cells also receive `metadata["wb2nb"]` describing the image source and classification.

## Output Contract

Forward conversion returns one HTML string.

Stable assumptions:

- includes `<!DOCTYPE html>`
- includes an `<html>` root
- converted article content lives under `#content`
- raw mode removes `<head>`, toolbar UI, and scripts

Details you should treat as implementation details:

- exact CSS
- toolbar copy text
- incidental wrapper class names
- JavaScript function names

## Related Helpers

- `nb2wb.supported_targets()`
- `nb2wb.load_input_payload()`
- `nb2wb.load_html_payload()`
- `nb2wb.load_notebook_payload()`
- `nb2wb.load_markdown_payload()`
- `nb2wb.load_quarto_payload()`
