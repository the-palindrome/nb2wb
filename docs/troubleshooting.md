# Troubleshooting

## `--execute` does not produce outputs

Check:

- Jupyter kernel is installed (`ipykernel`)
- kernel name in notebook metadata is valid
- runtime environment allows subprocess execution

In restricted CI/sandbox environments, execution may be blocked by policy.

## LaTeX renders differently than expected

Possible causes:

- no system `latex`/`dvipng` available, so fallback mathtext is used
- custom preamble only affects full usetex path

Check system tools and config (`latex.try_usetex`).

## Some external images disappear

`nb2wb` drops image tags it cannot convert safely.

Common reasons:

- URL points to non-public/private network address
- unsupported MIME type
- download fails timeout/size limits

## Conversion fails with safety limit errors

Adjust `safety` config values for your workload profile, for example:

- `max_input_bytes`
- `max_cells`
- `max_total_output_bytes`
- `max_display_math_blocks`

Only raise limits as needed.

## Medium/X paste issues

If embedded base64 images are stripped by editors:

- use `--serve` mode for public image URLs
- use per-image copy controls in generated pages

## Python API rejects notebook dict

Ensure payload is a valid notebook object with:

- `nbformat`
- `nbformat_minor`
- `cells` list
- `metadata`

Invalid payloads raise `ValueError`.
