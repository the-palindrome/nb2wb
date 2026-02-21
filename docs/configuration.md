# Configuration

Pass config through either:

- CLI: `-c config.yaml`
- API: `config=` as path, dict, or `Config` object

## Full Schema

```yaml
# Global defaults
image_width: 1920
border_radius: 14

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
  border_radius: 14

latex:
  font_size: 48
  dpi: 150
  color: "black"
  background: "white"
  padding: 68
  image_width: 1920
  try_usetex: true
  preamble: ""
  border_radius: 0

safety:
  max_input_bytes: 20971520
  max_cells: 2000
  max_cell_source_chars: 500000
  max_total_output_bytes: 26214400
  max_display_math_blocks: 500
  max_total_latex_chars: 1000000
```

## Inheritance Rules

- `code.image_width` and `latex.image_width` inherit top-level `image_width` unless overridden.
- `code.border_radius` and `latex.border_radius` inherit top-level `border_radius` unless overridden.

## Platform Defaults

When target is `medium` or `x`, platform defaults adjust canvas sizes and paddings for narrower layouts.

Examples:

- top-level `image_width`: `680`
- `code.font_size`: `42`
- `code.image_width`: `1200`
- `latex.font_size`: `35`
- `latex.padding`: `50`

Substack keeps base defaults unless overridden by your config.

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
