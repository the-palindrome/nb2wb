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

Execution:

- default: no execution
- with execute enabled: converted notebook model is executed

## In-Memory Notebook Payloads

Python API accepts parsed notebook objects directly:

- `dict` payload
- `nbformat.NotebookNode`

These payloads are normalized and validated before conversion.

## Cell Tags

| Tag | Behavior |
|---|---|
| `hide-cell` | Hide entire cell |
| `hide-input` | Hide code source |
| `hide-output` | Hide outputs |
| `latex-preamble` | Collect LaTeX preamble from cell/chunk |
| `text-snippet` | Render code as `<pre><code>` instead of PNG |
