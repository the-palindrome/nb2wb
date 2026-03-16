# Input Formats

## `.ipynb`

Behavior:

- reads notebook cells and outputs directly
- respects cell tags from `cell.metadata.tags`
- detects language from notebook metadata (`kernelspec` / `language_info`)

Execution:

- default: no execution
- with execute enabled: runs via Jupyter kernel before rendering

## `.md`

Supported features:

- optional YAML front matter
- fenced code blocks (backticks or tildes)
- fence-line tags (for example: ```` ```python hide-input ````)
- directives via HTML comments:
  - `<!-- nb2wb: hide-input -->`
  - `<!-- nb2wb: hide-output -->`
  - `<!-- nb2wb: hide-cell -->`
  - `<!-- nb2wb: text-snippet -->`
- special fence language: `latex-preamble`
- directive comments apply to the next fenced code block, and trailing
  directives with no following block are discarded

Execution:

- default: no execution
- with execute enabled: converted to notebook model, then executed

## `.qmd`

Supported features:

- optional YAML front matter
- Quarto fenced chunks (` ```{python} `)
- `#|` options mapped to tags:
  - `echo: false` -> `hide-input`
  - `output: false` -> `hide-output`
  - `include: false` / `eval: false` -> `hide-cell`
  - `tags: [...]` -> tag list
- special chunk languages:
  - `latex-preamble`
  - `output` (attaches stdout to immediately preceding code cell)
- `{output}` chunks only attach when they appear immediately after a code chunk;
  intervening prose breaks the association

Execution:

- default: no execution
- with execute enabled: converted notebook model is executed

## In-Memory Notebook Payloads

Python API accepts parsed notebook objects directly:

- `dict` payload
- `nbformat.NotebookNode`

These payloads are normalized and validated before conversion.

## In-Memory `.md` / `.qmd` Payloads

Python API also accepts in-memory text documents:

- raw `str` payload (auto-detected as Markdown or Quarto)
- mapping payloads:
  - `{"format": "md", "content": "<markdown text>"}`
  - `{"format": "qmd", "content": "<quarto text>"}`

Notes:

- mapping `format` aliases: `markdown`, `quarto`
- mapping `source` or `text` may be used instead of `content`
- plain strings that look like file paths are still treated as document text
- when auto-detection is ambiguous, prefer explicit mapping payloads
- file paths are loaded via `nb2wb.load_input_payload()` (or typed loader helpers), then passed to `nb2wb.convert()`

## `.html` / `.htm`

Supported for reverse conversion via `wb2nb` and `nb2wb.revert()`.

Behavior:

- parses the HTML document body (`<article>`, `<main>`, then `<body>`)
- converts prose HTML into markdown cells
- converts recognized code blocks into notebook code cells when the language is scaffold-supported
- preserves unsupported/unknown code blocks as fenced markdown
- keeps ordinary images as markdown images
- routes image content through the OCR pipeline and then converts typed OCR results into cells or linked figures

Current scaffold-supported code languages:

- `python`, `py`
- `r`
- `julia`, `jl`
- `bash`, `sh`, `shell`, `zsh`
- `javascript`, `js`
- `typescript`, `ts`
- `sql`

Notes:

- the built-in default OCR pipeline lives at `nb2wb.ocr.local`
- the OCR pipeline itself decides whether an image is treated as `figure`, `table`, `code`, or `latex`
- code OCR in the built-in pipeline uses `Tesseract` via `pytesseract` when installed and the `tesseract` binary is available on PATH; otherwise code-like images keep the linked-figure fallback
- LaTeX OCR and table OCR in the built-in pipeline use `Pix2Text` when installed; otherwise the reverse path keeps the image linked as a figure
- a placeholder multimodal OCR entrypoint lives at `nb2wb.ocr.multimodal_llm`
- the reverse path accepts in-memory HTML strings or `{"format": "html", "content": ...}` payloads
- file paths are loaded via `nb2wb.load_html_payload()`
- a custom OCR pipeline can be supplied via `nb2wb.revert(..., ocr_pipeline=...)`

## Cell Tags

| Tag | Behavior |
|---|---|
| `hide-cell` | Hide entire cell |
| `hide-input` | Hide code source |
| `hide-output` | Hide outputs |
| `latex-preamble` | Collect LaTeX preamble from cell/chunk and hide that cell from output |
| `text-snippet` | Render code as `<pre><code>` instead of PNG |
