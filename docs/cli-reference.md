# CLI Reference

`nb2wb` handles forward conversion. `wb2nb` handles reverse conversion.

## Forward Command

```text
nb2wb <input.{ipynb|qmd|md}> [options]
```

### Options

| Option | Meaning |
| --- | --- |
| `-t, --target {default,substack,medium,x,linkedin,devto,hashnode,ghost,wordpress}` | Publishing target profile |
| `-c, --config PATH` | YAML config path |
| `-o, --output PATH` | Output HTML path |
| `--image-strategy {embed,copyable}` | Override normal-mode image handling |
| `--raw-image-strategy {embed,copyable,preserve}` | Override raw-mode image handling |
| `--copy-script {simple,copyable,none}` | Override normal-mode copy script behavior |
| `--article-width INT` | Override wrapper max width in pixels |
| `--table-mode {native,image}` | Override table rendering mode |
| `--open` | Open the generated HTML after writing |
| `--serve` | Extract images, rewrite sources, and serve through localhost plus ngrok |
| `--execute` | Execute notebook code before rendering |
| `--warnings` | Render `stderr` streams |
| `--raw` | Remove preview chrome from the output |
| `--verbose` | Emit package debug logs to stderr |

`--image-strategy` intentionally exposes only `embed` and `copyable`. If you need to preserve original image sources, use API or YAML `target_options.image_strategy: preserve`.

### Common Recipes

```bash
nb2wb report.ipynb
nb2wb report.ipynb -t medium
nb2wb report.qmd -t x -o post.html
nb2wb examples/markdown.md --execute --warnings
nb2wb post.ipynb -t devto --copy-script none --article-width 780
nb2wb post.ipynb --raw -o post_raw.html
nb2wb post.ipynb --serve
nb2wb post.ipynb --verbose
```

### Execution and Output Semantics

- Execution is off by default.
- `--execute` works for `.ipynb`, `.md`, and `.qmd`.
- `stderr` stays hidden unless you add `--warnings`.
- If execution stops early, `nb2wb` still renders the notebook state that exists at that point.

### Raw Mode

Raw mode keeps the HTML shell but removes preview UI:

- no `<head>`
- no toolbar
- no JavaScript
- image behavior follows each target profile's `raw_image_strategy`

### Serve Mode

Use `--serve` when the destination editor strips base64 image sources.

The CLI:

1. extracts supported `data:` image URIs into `images/`
2. rewrites those image sources in the HTML
3. serves the output directory over localhost
4. starts an ngrok tunnel and opens the tunneled page

Requirements:

- `ngrok` installed
- `ngrok config add-authtoken <TOKEN>` completed

If you pass both `--serve` and `--open`, serve mode wins.

## Reverse Command

```text
wb2nb <input.{html|htm}> [options]
```

### Options

| Option | Meaning |
| --- | --- |
| `-o, --output PATH` | Output notebook path, default `<input>.ipynb` |
| `--ocr-pipeline {local,openai,gemini}` | Optional OCR pipeline |
| `--model MODEL` | Required for `openai` and `gemini` pipelines |
| `--verbose` | Emit package debug logs to stderr |

### Common Recipes

```bash
wb2nb article.html
wb2nb article.html -o recovered.ipynb
wb2nb examples/reverse_article.html
wb2nb article.html --ocr-pipeline local
OPENAI_API_KEY=... wb2nb article.html --ocr-pipeline openai --model your-model-name
GEMINI_API_KEY=... wb2nb article.html --ocr-pipeline gemini --model gemini-2.0-flash
GEMINI_API_KEY=... wb2nb article.html --ocr-pipeline gemini --model gemini-2.5-flash --verbose
```

### OCR Requirements

- `local` requires the OCR extra and system dependencies such as `tesseract`.
- `openai` requires `OPENAI_API_KEY`.
- `gemini` requires `GEMINI_API_KEY` or `GOOGLE_API_KEY`.
- `--model` is required for `openai` and `gemini`.
- `--verbose` prints package debug logs to stderr, including OCR progress and timing when OCR runs.

### Reverse-Conversion Behavior

- prose becomes markdown cells
- supported code blocks become code cells
- unsupported code blocks remain fenced markdown
- images remain linked unless OCR is enabled
- built-in OCR pipelines only read local paths and `data:` images

## Input Validation

The CLIs reject:

- unsupported file suffixes
- control characters in paths
- missing input files

For the full safety model, see [Security](security.md).
