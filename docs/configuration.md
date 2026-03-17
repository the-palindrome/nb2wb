# Configuration

Configuration controls rendering, safety limits, and wrapper behavior. You can pass it through the CLI with `-c config.yaml`, through the Python API as `config=...`, or keep it entirely in memory as a mapping.

The repository ships an opinionated example at `examples/config.yaml`. Use it as a starting point when you want a practical publication profile instead of the bare defaults.

## Full Schema

```yaml
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
  cache_size: 256
  border_radius: 0

table:
  mode: "native"
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
  image_strategy: null
  raw_image_strategy: null
  copy_script_mode: null
  article_width_px: null
  table_mode: null
  toolbar_message: null
  theme_overrides: {}
```

## Three Configuration Layers

`nb2wb` resolves configuration in this order:

1. Base config values
2. Target-profile render defaults
3. Runtime `target_options` overrides

That means you can keep a shared config file and still tweak the wrapper at call time without duplicating the whole schema.

## Inheritance Rules

- `code.image_width`, `latex.image_width`, and `table.image_width` inherit top-level `image_width` unless you override them.
- `code.border_radius`, `latex.border_radius`, and `table.border_radius` inherit top-level `border_radius` unless you override them.
- Unknown keys inside config sections are ignored.
- Invalid `table.mode` values fall back to `"native"`.

Hex colors are the most predictable option across renderers. Other Pillow and Matplotlib color strings may work, but hex keeps behavior easier to reason about.

## Render Controls

Use these when you want to tune output fidelity:

- `code.*` controls code image look and spacing.
- `latex.*` controls display-math rendering and optional `usetex` behavior.
- `table.*` controls native-vs-image table rendering and table image styling.

Useful recipes:

```yaml
table:
  mode: "image"
  shadow: false
```

Use that profile when table-heavy content matters more than card styling performance.

```yaml
latex:
  try_usetex: false
```

Use that when you want predictable mathtext behavior without depending on a system LaTeX installation.

## Safety Controls

The `safety` section protects backend workloads. These limits are always on in the normal conversion path.

The most common knobs are:

- `max_input_bytes`
- `max_cells`
- `max_cell_source_chars`
- `max_total_output_bytes`
- `max_display_math_blocks`
- `max_total_latex_chars`

Raise them only when a real workload needs it.

## Target Options

`target_options` changes wrapper behavior after rendering defaults have been applied.

Supported keys:

- `image_strategy`
- `raw_image_strategy`
- `copy_script_mode`
- `article_width_px`
- `table_mode`
- `toolbar_message`
- `theme_overrides`

Normal-mode `image_strategy` values:

- `embed`
- `copyable`
- `preserve` via API or YAML only

The CLI intentionally exposes only `embed` and `copyable` for `--image-strategy`. Use the API or YAML when you want to preserve existing image URLs exactly.

Example:

```yaml
target_options:
  article_width_px: 820
  table_mode: "image"
  toolbar_message: "Paste the article first, then copy any remaining images."
  theme_overrides:
    body-background: "#f7f7f7"
    content-background: "#ffffff"
    toolbar-background: "#111827"
```

`theme_overrides` merges with the selected profile theme. You only need to provide the keys you want to change.

## Platform Defaults

Target profiles automatically apply render defaults on top of your base config.

High-level families:

- `default`: no render overrides
- `substack`: image tables with roomy article layout
- `medium`, `x`, `linkedin`: narrower layouts with `copyable` image defaults
- `devto`, `hashnode`, `ghost`, `wordpress`: wider embed-first layouts

Built-in article widths:

- `medium`: `700`
- `x`: `680`
- `linkedin`: `760`
- `devto`: `860`
- `hashnode`: `840`
- `ghost`: `900`
- `wordpress`: `920`

## Python API Example

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
    "target_options": {
        "article_width_px": 760,
        "table_mode": "image",
    },
}
```
