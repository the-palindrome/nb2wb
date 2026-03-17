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
- local image path is absolute, traverses with `..`, or resolves outside the current working directory

If you need to keep original image URLs untouched, use API/YAML
`target_options.image_strategy: preserve`.

## `wb2nb` keeps images as markdown figures

This is the expected fallback when reverse conversion cannot safely or confidently turn an image into notebook content.

Common reasons:

- no `ocr_pipeline` was provided
- local OCR dependencies are missing
- the HTML references remote `http/https` images instead of local files or `data:` URIs
- the OCR pipeline classified the image as `figure`
- OCR failed and the pipeline fell back to the safe figure result

## Conversion fails with safety limit errors

Adjust `safety` config values for your workload profile, for example:

- `max_input_bytes`
- `max_cells`
- `max_total_output_bytes`
- `max_display_math_blocks`

Only raise limits as needed.

## Medium/X/LinkedIn paste issues

If embedded base64 images are stripped by editors:

- use `--serve` mode to generate a tunneled preview page with extracted `images/...` assets
- in normal mode, use per-image copy controls in generated pages
- in raw mode, copy controls are intentionally removed; prefer `--serve` or manual image handling

## Python API rejects notebook dict

Ensure payload is a valid notebook object with:

- `nbformat`
- `nbformat_minor`
- `cells` list
- `metadata`

Invalid payloads raise `ValueError`.

## Python API treated my file path string as document content

`nb2wb.convert()` does not load files. These calls behave differently:

- `nb2wb.convert("post.ipynb")` parses the string as Markdown text
- `nb2wb.convert(Path("post.ipynb"))` raises `TypeError`
- `nb2wb.convert(nb2wb.load_input_payload("post.ipynb"))` loads and converts the file

## Legacy notebook payload compatibility

`nb2wb` applies conservative compatibility normalization before conversion:

- upgrades legacy notebook majors to v4 (canonical internal target is v4.5)
- repairs known lossless legacy fields (`input`, `prompt_number`, `stream`, `pyout`, `pyerr`)
- fills/repairs missing or duplicate cell ids

If conversion still fails, the error category tells you why:

- `unsupported major version`: payload declares a newer major than supported
- `ambiguous legacy/malformed structure`: legacy shape cannot be upgraded safely
- `invalid/unrepairable schema fields`: payload contains unsupported/invalid fields

When this happens, validate the source notebook with `nbformat` and inspect top-level keys and code-cell output payload shapes.
