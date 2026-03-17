# Input Formats

This page maps each supported input shape to the features that matter during conversion.

## `.ipynb`

Notebook files are the most direct path through the converter. `nb2wb` reads existing cells and outputs, respects cell tags, and derives the notebook language from notebook metadata.

Key behaviors:

- reads existing markdown, code, and outputs directly
- respects `cell.metadata.tags`
- reads language from `kernelspec` or `language_info`
- executes only when you opt into `--execute` or `execute=True`

## `.md`

Markdown files are parsed into a notebook model first. This path is useful when you want notebook-style publishing without storing article content in `.ipynb`.

Markdown-specific features:

- optional YAML front matter
- fenced code blocks with backticks or tildes
- fence-line tags such as ```` ```python hide-output ````
- HTML comment directives such as `<!-- nb2wb: hide-input -->`
- special fence language `latex-preamble`

Supported directives:

- `hide-input`
- `hide-output`
- `hide-cell`
- arbitrary tags, including `text-snippet`

Directive comments apply to the next fenced block. Trailing directives with no following block are ignored on purpose.

## `.qmd`

Quarto documents are also parsed into a notebook model first, but with Quarto-specific chunk rules.

Quarto-specific features:

- YAML front matter
- chunk syntax such as ```` ```{python} ````
- `#|` cell options at the top of a chunk
- special chunk types `latex-preamble` and `output`

Option mapping:

| Quarto option | Resulting tag |
| --- | --- |
| `#| echo: false` | `hide-input` |
| `#| output: false` | `hide-output` |
| `#| include: false` | `hide-cell` |
| `#| eval: false` | `hide-cell` |
| `#| tags: [...]` | arbitrary tags |

`{output}` chunks attach precomputed stdout to the immediately preceding code chunk. If prose appears between them, the attachment is intentionally broken.

## In-Memory Notebook Payloads

The Python API accepts notebook payloads directly as:

- `dict`
- `nbformat.NotebookNode`

These inputs are normalized to internal `nbformat=4`, `nbformat_minor=5` before rendering. Conservative compatibility repairs cover older worksheet notebooks, duplicate or missing cell ids, and a small set of legacy code/output field names.

## In-Memory Text Payloads

The Python API also accepts text directly:

- raw `str` payloads
- `{"format": "md", "content": "..."}`
- `{"format": "qmd", "content": "..."}`

Format aliases:

- `markdown` -> `md`
- `quarto` -> `qmd`

Content aliases:

- `content`
- `source`
- `text`

Plain strings that look like paths are still treated as document text. Use loader helpers when the source is actually a file on disk.

## `.html` / `.htm`

HTML input is supported for reverse conversion through `wb2nb` and `nb2wb.revert()`.

Reverse-conversion behavior:

- chooses `<article>`, then `<main>`, then `<body>` as the content root
- turns prose HTML into markdown cells
- turns supported code blocks into code cells
- preserves unsupported code blocks as fenced markdown
- keeps images linked unless OCR is enabled

Supported scaffold languages:

- `python`
- `r`
- `julia`
- `bash`
- `javascript`
- `typescript`
- `sql`

## Loader Helpers

Use loader helpers when the source is a path:

| Helper | Input | Output |
| --- | --- | --- |
| `load_input_payload()` | `.ipynb`, `.md`, `.qmd` | notebook payload or text payload |
| `load_notebook_payload()` | `.ipynb` | validated `NotebookNode` |
| `load_markdown_payload()` | `.md` | Markdown payload mapping |
| `load_quarto_payload()` | `.qmd` | Quarto payload mapping |
| `load_html_payload()` | `.html`, `.htm` | HTML payload mapping with `source_dir` |

`load_html_payload()` includes `source_dir` so reverse conversion can resolve relative image paths.

## Cell Tags

These tags affect the forward converter regardless of where they came from:

| Tag | Effect |
| --- | --- |
| `hide-cell` | Skip the entire cell |
| `hide-input` | Hide source code and show outputs only |
| `hide-output` | Hide outputs and show source only |
| `latex-preamble` | Extend the LaTeX preamble and hide the cell |
| `text-snippet` | Render code as escaped HTML text instead of an image |
