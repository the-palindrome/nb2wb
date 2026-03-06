# Platforms

`nb2wb` generates target-profiled HTML wrappers.

## Supported Targets

- `default`
- `substack`
- `medium`
- `x`
- `linkedin`
- `devto`
- `hashnode`
- `ghost`
- `wordpress`

## Default Image Strategies

- `copyable`: `medium`, `x`, `linkedin`
- `embed`: `default`, `substack`, `devto`, `hashnode`, `ghost`, `wordpress`

You can override these defaults via:

- CLI: `--image-strategy`, `--raw-image-strategy`, `--copy-script`
- API: `target_options={...}`
- YAML: `target_options: ...`

## Raw Mode Across Targets

Use `--raw` (CLI) or `raw_mode=True` (Python API) to remove preview chrome from output:

- no `<head>` section
- no toolbar/header copy controls
- no JavaScript blocks
- image behavior still follows each target profile's `raw_image_strategy`

## Target Notes

- `default`: neutral preview mode (generic title/message, no platform-specific render defaults).
- `substack`: embed-first workflow with simple copy toolbar.
- `medium`: copyable image wrappers in normal mode.
- `x`: copyable image wrappers in normal mode, narrow article layout defaults.
- `linkedin`: copyable image wrappers in normal mode.
- `devto`, `hashnode`, `ghost`, `wordpress`: embed-first defaults and direct paste flow.

## `--serve` Mode

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
