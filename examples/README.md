# Examples

This directory is a practical companion to the docs. Every file is meant to demonstrate a real feature combination, not just exist as a placeholder.

## Recommended Tour

From the repository root:

```bash
nb2wb examples/notebook.ipynb -o examples/notebook.html
nb2wb examples/markdown.md --execute --warnings -o examples/markdown.html
nb2wb examples/quarto.qmd -o examples/quarto.html
python3 examples/convert_notebook_api.py
wb2nb examples/reverse_article.html -o examples/reverse_article.ipynb
python3 examples/revert_html_api.py
```

Add a target profile when you want to inspect platform-specific wrapping:

```bash
nb2wb examples/notebook.ipynb -t medium -o examples/medium_preview.html
nb2wb examples/x_article.ipynb -t x -o examples/x_article.html
nb2wb examples/notebook.ipynb --serve
```

## Files and Purpose

| File | Purpose |
| --- | --- |
| `notebook.ipynb` | Full notebook example with tags, figures, rich outputs, and narrative structure |
| `markdown.md` | Markdown example with front matter, directives, fence tags, tables, figures, and execute-time rich outputs |
| `quarto.qmd` | Quarto example with front matter, `#|` options, arbitrary tags, `{output}` chunks, and publication-oriented sections |
| `x_article.ipynb` | Shorter article tuned for the X Articles workflow |
| `reverse_article.html` | Reverse-conversion source with prose, supported code, unsupported code, and local images |
| `config.yaml` | Opinionated publication config that demonstrates practical render and wrapper settings |
| `convert_notebook_api.py` | Forward-conversion API example that writes normal and raw outputs |
| `revert_html_api.py` | Reverse-conversion API example that writes a scaffolded notebook |
| `image.png` | Shared local image asset used by forward and reverse examples |

## Forward-Conversion Coverage

| Feature | `notebook.ipynb` | `markdown.md` | `quarto.qmd` |
| --- | ---: | ---: | ---: |
| Inline math | ✅ | ✅ | ✅ |
| Display math | ✅ | ✅ | ✅ |
| `\label` and `\eqref` | ✅ | ✅ | ✅ |
| `latex-preamble` support | ✅ | ✅ | ✅ |
| Tables | ✅ | ✅ | ✅ |
| Local images | ✅ | ✅ | ✅ |
| Code rendered as image | ✅ | ✅ | ✅ |
| `text-snippet` rendering | ✅ | ✅ | ✅ |
| `hide-input` | ✅ | ✅ | ✅ |
| `hide-output` | ✅ | ✅ | ✅ |
| `hide-cell` | ✅ | ✅ | ✅ |
| Markdown directive comments | n/a | ✅ | n/a |
| Markdown front matter | n/a | ✅ | n/a |
| Quarto `#|` option mapping | n/a | n/a | ✅ |
| Quarto `{output}` chunk attachment | n/a | n/a | ✅ |
| Execute-time HTML output | - | ✅ | ✅ |
| Execute-time SVG output | - | ✅ | ✅ |
| Execute-time `stderr` demo | n/a | ✅ | n/a |

## Reverse-Conversion Coverage

`reverse_article.html` demonstrates these reverse behaviors:

- prose becomes markdown cells
- recognized Python code becomes a code cell
- unsupported Mermaid code stays fenced in markdown
- a local image remains linked unless OCR is enabled
- image captions and nearby text are available to OCR pipelines through context

## Notes

- `markdown.md` is the best single example for forward-conversion features that need `--execute` or `--warnings`.
- `quarto.qmd` is the best example when you want to inspect how `#|` options and `{output}` chunks map into notebook behavior.
- `reverse_article.html` is the best starting point for testing `wb2nb` and custom OCR contracts.
