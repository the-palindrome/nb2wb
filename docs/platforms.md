# Platforms

`nb2wb` ships target profiles for common publishing destinations. A profile controls wrapper styling, default image strategy, copy affordances, and a small set of render defaults.

## Supported Targets

| Target | Default image strategy | Article width | Typical use |
| --- | --- | ---: | --- |
| `default` | `embed` | base config | neutral preview |
| `substack` | `embed` | base config | copy into Substack with image tables |
| `medium` | `copyable` | `700px` | copy into Medium with per-image helpers |
| `x` | `copyable` | `680px` | X Articles workflow |
| `linkedin` | `copyable` | `760px` | LinkedIn article workflow |
| `devto` | `embed` | `860px` | embed-first dev blog workflow |
| `hashnode` | `embed` | `840px` | embed-first dev blog workflow |
| `ghost` | `embed` | `900px` | wider editorial layout |
| `wordpress` | `embed` | `920px` | wider editorial layout |

All built-in targets use `embed` in raw mode unless you override `raw_image_strategy`.

## Image Strategy Defaults

Normal mode profile defaults:

- `copyable`: `medium`, `x`, `linkedin`
- `embed`: `default`, `substack`, `devto`, `hashnode`, `ghost`, `wordpress`

Available override values:

- `embed`
- `copyable`
- `preserve`

Use `preserve` through the Python API or YAML when you want to keep existing image sources untouched.

## Raw Mode Across Targets

Use `--raw` or `raw_mode=True` when you want article HTML without preview chrome.

Raw mode removes:

- `<head>`
- toolbar/header UI
- JavaScript

The HTML shell still includes `<!DOCTYPE html>`, `<html>`, `<body>`, and `#content`.

## Target Profile Families

### Neutral and Embed-First

- `default`
- `substack`
- `devto`
- `hashnode`
- `ghost`
- `wordpress`

These are good choices when embedded images are acceptable and you want a clean, low-friction preview page.

### Copyable-Image Workflows

- `medium`
- `x`
- `linkedin`

These profiles assume the destination editor may need individual image copy actions in normal mode.

## Wrapper Overrides

Keep the target profile when it is close to what you want, then adjust the wrapper through `target_options`.

Common keys:

- `article_width_px`
- `toolbar_message`
- `copy_script_mode`
- `image_strategy`
- `raw_image_strategy`
- `table_mode`
- `theme_overrides`

Example:

```python
import nb2wb

html = nb2wb.convert(
    notebook_payload,
    target="medium",
    target_options={
        "article_width_px": 760,
        "toolbar_message": "Paste the article first, then copy any remaining images from the preview.",
        "theme_overrides": {
            "body-background": "#faf7f2",
            "content-background": "#ffffff",
            "toolbar-background": "#14532d",
        },
    },
)
```

`theme_overrides` merges with the selected profile theme. You do not need to replace the whole theme to make one small adjustment.

## `--serve` for Copyable Workflows

`--serve` is not a target profile, but it is often used with `medium`, `x`, and `linkedin`.

The flow:

1. convert the article
2. extract supported `data:` images into files
3. rewrite the HTML to use those files
4. serve the page locally and through ngrok

Use it when the destination editor strips embedded images and you still want a paste-oriented preview.
