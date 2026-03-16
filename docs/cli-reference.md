# CLI Reference

## Command

```text
nb2wb <input.{ipynb|qmd|md}> [options]
wb2nb <input.{html|htm}> [options]
```

## Options

| Option | Description |
|---|---|
| `-t, --target {default,substack,medium,x,linkedin,devto,hashnode,ghost,wordpress}` | Target platform (`default` default mode) |
| `-c, --config PATH` | Config YAML path |
| `-o, --output PATH` | Output HTML path |
| `--image-strategy {embed,copyable}` | Override normal-mode image behavior |
| `--raw-image-strategy {embed,copyable,preserve}` | Override raw-mode image behavior |
| `--copy-script {simple,copyable,none}` | Override non-raw copy script mode |
| `--article-width INT` | Override preview wrapper max width (px) |
| `--table-mode {native,image}` | Override table rendering mode |
| `--open` | Open generated HTML in browser |
| `--serve` | Extract image data URIs into `images/` beside the output and serve the page over local HTTP + ngrok |
| `--execute` | Execute code cells before rendering |
| `--warnings` | Render `stderr` warning/log outputs from code cells |
| `--raw` | Emit raw output (no `<head>`, toolbar, or JavaScript) |

Normal-mode `--image-strategy` intentionally exposes only `embed` and
`copyable`. If you need to preserve existing `<img src="...">` values, use the
Python API or YAML `target_options.image_strategy: preserve`.

## Examples

```bash
nb2wb report.ipynb
nb2wb report.ipynb -t medium
nb2wb report.qmd -t x -o post.html
nb2wb post.ipynb -t linkedin --image-strategy copyable
nb2wb post.ipynb -t devto --copy-script none --article-width 780
nb2wb notes.md --execute
nb2wb report.ipynb --warnings
nb2wb report.ipynb --serve
nb2wb report.ipynb --raw -o post_raw.html
wb2nb article.html
wb2nb article.htm -o recovered.ipynb
wb2nb article.html --ocr-pipeline local
OPENAI_API_KEY=... wb2nb article.html --ocr-pipeline openai --model your-model-name
```

## Reverse Conversion

`wb2nb` converts HTML posts into scaffolded Jupyter notebooks.

| Option | Description |
|---|---|
| `-o, --output PATH` | Output notebook path (default: `<input>.ipynb`) |
| `--ocr-pipeline {local,openai}` | Optional OCR pipeline for image-based reverse conversion; if omitted, OCR is skipped |
| `--model MODEL` | Required when `--ocr-pipeline openai`; selects the model |

Current reverse-conversion behavior:

- prose HTML is converted into markdown cells
- recognized HTML code blocks become notebook code cells for scaffold-supported languages
- unsupported/unknown code languages are preserved as fenced markdown code blocks
- if `--ocr-pipeline` is omitted, images remain linked markdown figures with no transcription
- if `--ocr-pipeline` is provided, every image is passed to the selected OCR pipeline with its HTML context
- the OCR pipeline decides whether each image is treated as a linked figure or converted into code/markdown notebook content
- `openai` requires `OPENAI_API_KEY` in the environment and fails fast on missing credentials or API errors
- the built-in OCR pipelines only process local paths and `data:` images; remote `http/https` image URLs keep the figure fallback

For a fuller workflow guide, see [Reverse Conversion](reverse-conversion.md).

## Execution Semantics

- Execution is off by default.
- `--execute` applies uniformly to `.ipynb`, `.qmd`, and `.md`.
- `stderr` warning/log streams are hidden by default; use `--warnings` to render them.
- If execution stops early, conversion continues with the notebook state that is
  available at that point and emits a warning.

## Raw Mode

- `--raw` strips preview wrapper chrome from output.
- Raw output omits the entire `<head>` section.
- Raw output omits all JavaScript (`<script>` blocks).
- Raw image behavior follows each target profile's `raw_image_strategy`, overrideable via `--raw-image-strategy`.
- `--raw --serve` is supported: image data URIs are still extracted/relinked for serving, while the served page remains raw (no `<head>`, toolbar, or JavaScript).

## Serve Mode

- `--serve` writes extracted image files to `images/` under the output directory.
- The CLI rewrites recognized image `data:` URIs to relative `images/...` paths
  before serving.
- Unknown image MIME types or malformed data URIs are left unchanged.
- The CLI serves the output directory on localhost, starts an ngrok tunnel, and opens the tunneled page in your browser.
- If both `--serve` and `--open` are provided, `--serve` takes precedence.
- Use this mode when a target editor strips embedded base64 images but you still want a copy/paste-oriented preview.

## Input Validation

The CLI rejects:

- unsupported input suffixes
- control characters in input, output, and config paths
- missing input file paths

For full safety model details, see [Security](security.md).
