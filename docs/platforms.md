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
- `preserve`: available only as an API/YAML override, not as a built-in target default

You can override these defaults via:

- CLI: `--image-strategy`, `--raw-image-strategy`, `--copy-script`
- API: `target_options={...}`
- YAML: `target_options: ...`

The normal-mode CLI flag `--image-strategy` exposes `embed` and `copyable`.
Use API/YAML `image_strategy: preserve` when you need to keep existing image
URLs or relative paths untouched.

## Raw Mode Across Targets

Use `--raw` (CLI) or `raw_mode=True` (Python API) to remove preview chrome from output:

- no `<head>` section
- no toolbar/header copy controls
- no JavaScript blocks
- image behavior still follows each target profile's `raw_image_strategy`
- output still remains a complete HTML document with `<!DOCTYPE html>`,
  `<html>`, `<body>`, and `#content`

## Target Notes

- `default`: neutral preview mode (generic title/message, no platform-specific render defaults).
- `substack`: embed-first workflow with simple copy toolbar.
- `medium`: copyable image wrappers in normal mode.
- `x`: copyable image wrappers in normal mode, narrow article layout defaults.
- `linkedin`: copyable image wrappers in normal mode.
- `devto`, `hashnode`, `ghost`, `wordpress`: embed-first defaults and direct paste flow.

## Wrapper Customization

Use `target_options` when you want to keep a target profile but tune the wrapper around it.
This is the main place to override toolbar copy behavior, article width, helper text, and preview theme variables.

Example:

```python
import nb2wb

html = nb2wb.convert(
    notebook_payload,
    target="medium",
    target_options={
        "article_width_px": 760,
        "toolbar_message": "Paste into Medium, then copy any missing images from the preview.",
        "theme_overrides": {
            "body-background": "#faf7f2",
            "content-background": "#ffffff",
            "toolbar-background": "#14532d",
        },
    },
)
```

Useful override keys include:

- `article_width_px`
- `toolbar_message`
- `copy_script_mode`
- `image_strategy`
- `raw_image_strategy`
- `table_mode`
- `theme_overrides`

Common `theme_overrides` keys include:

- `body-background`
- `body-max-width`
- `content-background`
- `content-padding`
- `toolbar-background`
- `toolbar-button-background`
- `link-color`

Profile theme overrides merge with the selected target theme.
You only need to provide the keys you want to change.

## `--serve` Mode

`--serve` converts embedded image data URIs into extracted image files and then
serves the output directory through localhost and ngrok.

Flow:

1. extract images from generated HTML
2. write files to `images/`
3. rewrite image sources to relative `images/...` paths
4. expose the page via local server + ngrok tunnel

Requirements:

- `ngrok` installed
- authenticated ngrok configuration

If both `--serve` and `--open` are passed, the serve flow opens the tunneled
page and `--open` is effectively ignored.

## Choosing a Target Programmatically

```python
import nb2wb

for target in nb2wb.supported_targets():
    html = nb2wb.convert(notebook_payload, target=target)
```
