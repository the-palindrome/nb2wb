# Feature Tour

This page follows the same path as the converter itself: source content comes in, the notebook model is normalized, cells are rendered, output is wrapped for a target, and the reverse path remains available when you need to go back.

## 1. Start From the Source You Already Have

`nb2wb` accepts Jupyter notebooks, Markdown, and Quarto. The package also accepts the same content as in-memory payloads, which is what makes it easy to use inside APIs and worker services.

Forward inputs:

- `.ipynb`
- `.md`
- `.qmd`
- in-memory notebook payloads
- in-memory Markdown and Quarto payloads

Reverse inputs:

- `.html`
- `.htm`
- in-memory HTML payloads

## 2. Normalize Everything Into One Notebook Model

Markdown and Quarto sources are parsed into notebook cells before rendering. Notebook payloads are validated and normalized first, including conservative compatibility repairs for older payload shapes.

That shared model is what keeps the rendering path consistent across input formats. Once the notebook exists in memory, the converter no longer cares whether it started life as `.ipynb`, `.md`, or `.qmd`.

## 3. Render Markdown, Math, Code, and Outputs

The renderer handles notebook content type by type:

| Content | Rendered form |
| --- | --- |
| Inline math | Readable Unicode text |
| Display math | PNG image |
| Code input | Syntax-highlighted PNG, or `<pre><code>` with `text-snippet` |
| Stream and error output | PNG image |
| `image/png` output | Embedded image |
| `image/svg+xml` output | Sanitized SVG data URI |
| `text/html` output | Sanitized HTML fragment |
| Tables | Native HTML or PNG image |

Several notebook-level features carry across the whole document:

- `\label{...}` and `\eqref{...}` work across markdown cells.
- `latex-preamble` cells extend the LaTeX preamble without rendering themselves.
- `hide-cell`, `hide-input`, and `hide-output` control visibility at the cell level.

## 4. Decide How Much Runtime Behavior You Want

Execution is off by default. Turn it on only when the source needs fresh outputs:

- CLI: `--execute`
- Python API: `execute=True`

When execution is on, `nb2wb` uses a Jupyter kernel before rendering. If execution stops early, conversion still continues with the notebook state that is available at that point.

`stderr` stays hidden by default because many publishing flows treat warnings as noise. Add `--warnings` or `warnings_mode=True` when those streams are part of the story.

## 5. Wrap the Result for a Publishing Target

After rendering, `nb2wb` wraps the article in one of the built-in target profiles:

- `default`
- `substack`
- `medium`
- `x`
- `linkedin`
- `devto`
- `hashnode`
- `ghost`
- `wordpress`

Targets mainly differ in wrapper styling, default image strategy, article width, and copy controls. You can keep the profile and still override pieces like `image_strategy`, `table_mode`, or `toolbar_message`.

## 6. Switch Between Preview Mode and Raw Mode

Normal mode gives you a full preview page with wrapper CSS, toolbar text, and copy helpers. Raw mode strips that chrome and returns a minimal HTML shell around the converted article body.

Use normal mode when you want a guided copy-and-paste workflow. Use raw mode when you want the article HTML without preview UI.

## 7. Use `--serve` When Editors Reject Embedded Images

Some editors strip base64 image sources. `--serve` works around that by extracting image data URIs to files, rewriting the HTML to point at those files, and serving the result through localhost plus ngrok.

This mode is especially useful for `copyable` image workflows on Medium, X, and LinkedIn.

## 8. Reverse HTML Back Into a Notebook Scaffold

`wb2nb` and `nb2wb.revert()` recover article structure conservatively:

- prose becomes markdown cells
- supported code blocks become code cells
- unsupported code blocks stay fenced in markdown
- ordinary images stay linked as markdown figures

OCR is optional. When you provide a pipeline, images can become notebook cells for `latex`, `table`, or `code` results. When OCR is off or uncertain, the safe fallback is still a linked figure.

## 9. Keep the Safe Path On by Default

The conversion path always applies:

- HTML and SVG sanitization
- CSS URL filtering
- SSRF-safe remote image fetching
- local path traversal protection
- notebook size and workload limits

That safety posture is part of the default product behavior, not an optional mode.
