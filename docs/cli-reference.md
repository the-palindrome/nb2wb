# CLI Reference

## Command

```text
nb2wb <input.{ipynb|qmd|md}> [options]
```

## Options

| Option | Description |
|---|---|
| `-t, --target {substack,medium,x}` | Target platform (`substack` default) |
| `-c, --config PATH` | Config YAML path |
| `-o, --output PATH` | Output HTML path |
| `--open` | Open generated HTML in browser |
| `--serve` | Extract images and expose via local server + ngrok |
| `--execute` | Execute code cells before rendering |
| `--raw` | Emit raw output (no `<head>`, toolbar, or JavaScript) |

## Examples

```bash
nb2wb report.ipynb
nb2wb report.ipynb -t medium
nb2wb report.qmd -t x -o post.html
nb2wb notes.md --execute
nb2wb report.ipynb --serve
nb2wb report.ipynb --raw -o post_raw.html
```

## Execution Semantics

- Execution is off by default.
- `--execute` applies uniformly to `.ipynb`, `.qmd`, and `.md`.
- Execution failures are reported as warnings and conversion continues with available state.

## Raw Mode

- `--raw` strips preview wrapper chrome from output.
- Raw output omits the entire `<head>` section.
- Raw output omits all JavaScript (`<script>` blocks).
- For `medium` and `x` targets, raw mode emits plain `<img ...>` tags (no `.image-container` / copy-image button wrappers).
- `--raw --serve` is supported: image data URIs are still extracted/relinked for serving, while the served page remains raw (no `<head>`, toolbar, or JavaScript).

## Input Validation

The CLI rejects:

- unsupported input suffixes
- control characters in CLI paths
- missing input file paths

For full safety model details, see [Security](security.md).
