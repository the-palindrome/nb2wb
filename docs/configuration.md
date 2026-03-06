# Configuration

Pass config through either:

- CLI: `-c config.yaml`
- API: `config=` as path, dict, or `Config` object

## Full Schema

```yaml
# Global defaults
image_width: 1920
border_radius: 0

code:
  font_size: 48
  theme: "monokai"
  line_numbers: true
  font: "DejaVu Sans Mono"
  image_width: 1920
  padding_x: 100
  padding_y: 100
  separator: 0
  background: ""
  border_radius: 0

latex:
  font_size: 48
  dpi: 150
  color: "#000000"
  background: "#ffffff"
  padding: 68
  image_width: 1920
  try_usetex: true
  preamble: ""
  cache_size: 256          # max LaTeX render cache entries (0 disables cache)
  border_radius: 0

table:
  mode: "native"          # "native" (HTML table) or "image" (render table as PNG)
  font_size: 34
  font: "DejaVu Sans"
  color: "#1f2937"
  header_color: "#0f172a"
  background: "#ffffff"
  header_background: "#eef2ff"
  stripe_background: "#f8fafc"
  border_color: "#dbe4ee"
  border_width: 1
  cell_padding_x: 24
  cell_padding_y: 14
  outer_padding: 20
  canvas_background: "#ffffff"
  zebra_striping: true
  shadow: true
  shadow_color: "#0f172a"
  shadow_alpha: 24
  shadow_offset_x: 0
  shadow_offset_y: 8
  shadow_blur: 18
  image_width: 1920
  border_radius: 0

safety:
  max_input_bytes: 20971520
  max_cells: 2000
  max_cell_source_chars: 500000
  max_total_output_bytes: 26214400
  max_display_math_blocks: 500
  max_total_latex_chars: 1000000

target_options:
  image_strategy: null         # "embed" | "copyable" | "preserve"
  raw_image_strategy: null     # "embed" | "copyable" | "preserve"
  copy_script_mode: null       # "simple" | "copyable" | "none"
  article_width_px: null       # positive integer
  table_mode: null             # "native" | "image"
  toolbar_message: null        # custom toolbar helper text
  theme_overrides: {}          # CSS variable map for wrapper theme
```

## Inheritance Rules

- `code.image_width`, `latex.image_width`, and `table.image_width` inherit top-level `image_width` unless overridden.
- `code.border_radius`, `latex.border_radius`, and `table.border_radius` inherit top-level `border_radius` unless overridden.
- Color fields use hex format (for example `#ffffff`, `#000000`, `#ff0000`).

## Default Behavior

- If top-level `border_radius` is omitted, it defaults to `0`.
- Sub-config border radii inherit that value unless explicitly set.

## Platform Defaults

Target profiles apply render defaults automatically for each supported target:

- `default`
- `substack`
- `medium`
- `x`
- `linkedin`
- `devto`
- `hashnode`
- `ghost`
- `wordpress`

Examples:

- `default`: no render overrides; uses base config values
- top-level `image_width`:
  - `700` for `medium`
  - `680` for `x`
  - `760` for `linkedin`
  - `860` for `devto`
  - `840` for `hashnode`
  - `900` for `ghost`
  - `920` for `wordpress`
- `code.font_size`: `42`
- `code.image_width`: `1200`
- `latex.font_size`: `35`
- `latex.padding`: `50`

Table fallback defaults by platform:

- `substack`: `table.mode: "image"`
- `medium` / `x` / `linkedin`: `table.mode: "image"` (+ narrow-layout table defaults)
- `devto` / `hashnode` / `ghost` / `wordpress`: `table.mode: "image"` (+ medium-width defaults)

## Fast Table Rendering (Opt-In)

If runtime is more important than drop-shadow styling, disable table shadows:

```yaml
table:
  mode: "image"
  shadow: false
```

This keeps table images enabled while reducing render cost on table-heavy documents.

## API Dict Example

```python
config = {
    "image_width": 1600,
    "code": {
        "theme": "github-dark",
        "font_size": 42,
    },
    "latex": {
        "try_usetex": True,
        "preamble": "\\usepackage{amsmath}",
    },
    "safety": {
        "max_cells": 1500,
        "max_total_output_bytes": 20 * 1024 * 1024,
    },
}
```
