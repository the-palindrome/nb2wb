# Examples

This directory contains synchronized, feature-focused examples for every
supported input format.

## Quick start

From repository root:

```bash
nb2wb examples/notebook.ipynb -o examples/notebook.html
nb2wb examples/markdown.md -o examples/markdown.html
nb2wb examples/markdown.md --execute -o examples/markdown_exec.html
nb2wb examples/quarto.qmd -o examples/quarto.html
nb2wb examples/notebook.ipynb -t medium -o examples/medium_preview.html
nb2wb examples/notebook.ipynb -t x -o examples/x_preview.html
```

To test URL-based image workflows for Medium/X:

```bash
nb2wb examples/notebook.ipynb -t medium --serve
```

## Files and purpose

| File | Format | Purpose |
|---|---|---|
| `notebook.ipynb` | Jupyter notebook | Full notebook-mode feature demo, including tags and rich outputs |
| `markdown.md` | Markdown | Full Markdown-mode demo, including directives and optional `--execute` behavior |
| `quarto.qmd` | Quarto | Full Quarto-mode demo, including `#|` options and `{output}` chunks |
| `x_article.ipynb` | Jupyter notebook | Short, publication-style example tuned for X Articles workflow |
| `config.yaml` | YAML | Annotated configuration reference with practical publication settings |
| `image.png` | asset | Local image used by Markdown/Quarto/Notebook examples |

## Feature coverage matrix

| Feature | `notebook.ipynb` | `markdown.md` | `quarto.qmd` |
|---|---:|---:|---:|
| Inline math (`$...$`) | ✅ | ✅ | ✅ |
| Display math (`$$...$$`, environments) | ✅ | ✅ | ✅ |
| `\label` + `\eqref` | ✅ | ✅ | ✅ |
| `latex-preamble` support | ✅ | ✅ | ✅ |
| Code as rendered PNG | ✅ | ✅ | ✅ |
| `text-snippet` rendering | ✅ | ✅ | ✅ |
| `hide-input` | ✅ | ✅ | ✅ |
| `hide-output` | ✅ | ✅ | ✅ |
| `hide-cell` | ✅ | ✅ | ✅ |
| Stream output rendering | ✅ | ✅ (`--execute`) | ✅ |
| `image/png` output | ✅ | ✅ (`--execute`) | ✅ |
| `image/svg+xml` output | ✅ | ✅ (`--execute`) | ✅ |
| `text/html` output | ✅ | ✅ (`--execute`) | ✅ |
| Markdown directive comments | n/a | ✅ | n/a |
| Quarto `#|` option mapping | n/a | n/a | ✅ |
| Quarto `{output}` chunk attachment | n/a | n/a | ✅ |

## Notes

- `.md` examples only produce code outputs when `--execute` is enabled.
- `.qmd` examples are always executed by design.
- SVG/HTML examples intentionally include unsafe constructs (`<script>`,
  inline events, `javascript:`) so you can verify sanitization behavior.
