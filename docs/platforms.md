# Platforms

`nb2wb` generates platform-targeted HTML wrappers.

## Supported Targets

- `substack`
- `medium`
- `x`

## Raw Mode Across Targets

Use `--raw` (CLI) or `raw_mode=True` (Python API) to remove preview chrome from output:

- no `<head>` section
- no toolbar/header copy controls
- no JavaScript blocks
- for `medium` and `x`, images are plain `<img ...>` tags without copy-button wrappers

## Substack

- best fit for direct copy/paste with embedded data URI images
- includes copy toolbar for article content
- markdown tables default to image fallback for reliable paste fidelity

## Medium

- copy/paste-friendly wrapper
- per-image copy controls included
- medium editor behavior may still require per-image insertion depending on editor changes
- markdown tables default to image fallback for reliable rendering

## X Articles

- similar workflow to Medium
- includes copy controls for reliable transfer
- markdown tables default to image fallback for reliable rendering

## `--serve` Mode for Medium/X

`--serve` rewrites embedded image data URIs to hosted image URLs via local static serving + ngrok.

Flow:

1. extract images from generated HTML
2. write files to `images/`
3. rewrite image sources to HTTP URLs
4. expose via local server + ngrok tunnel

Requirements:

- `ngrok` installed
- authenticated ngrok configuration

## Choosing a Target Programmatically

```python
import nb2wb

for target in nb2wb.supported_targets():
    html = nb2wb.convert(notebook_payload, target=target)
```
