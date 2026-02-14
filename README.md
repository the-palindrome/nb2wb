# nb2wb

**Write in Jupyter Notebooks. Publish anywhere.**

`nb2wb` (short for *notebook to web*) converts Jupyter Notebooks into self-contained HTML files you can
paste directly into publishing platforms like **Substack** and **X Articles** — with LaTeX, code, and outputs all
rendered faithfully.

---

## Why

Most web publishing platforms strip MathJax and code-block formatting. `nb2wb` sidesteps
this by turning complex content into **images**, and converting simple inline math into
**Unicode text** that pastes cleanly as prose.

| Notebook element | nb2wb output |
|---|---|
| Inline LaTeX `$...$` | Unicode text (α, β, ∇, ℝ, …) |
| Display math `$$...$$`, `\[...\]`, `\begin{equation}` | PNG image |
| Code cells | Syntax-highlighted PNG image |
| Cell outputs (text, repr, …) | PNG image |
| Cell outputs (matplotlib figure, …) | Embedded PNG / SVG |

---

## Installation

```bash
git clone https://github.com/yourname/nb2wb.git
cd nb2wb
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

To run the bundled example notebooks (which use NumPy), install the optional
`examples` extra:

```bash
pip install -e ".[examples]"
```

---

## Usage

```bash
nb2wb notebook.ipynb                         # → notebook.html (Substack by default)
nb2wb notebook.ipynb -t x                    # → X Articles format
nb2wb notebook.ipynb -c config.yaml          # with custom config
nb2wb notebook.ipynb -o out.html             # explicit output path
nb2wb notebook.ipynb --open                  # open in browser when done
```

Then open the HTML file in your browser, click **Copy to clipboard**, and
paste into your platform's draft editor.

### Supported platforms

| Platform | Flag | How it works |
|---|---|---|
| **Substack** | `-t substack` (default) | Copy HTML and paste directly into Substack editor |
| **X Articles** | `-t x` | Interactive HTML with "Copy image" buttons — click each button to copy images to clipboard, then paste into X editor |

**Note for X Articles:** X's editor doesn't support embedded images, so nb2wb generates an interactive HTML page. Click the "Copy image" button for each image, paste it into your X draft at the right position, then copy-paste the text content around the images.

---

## Configuration

All options are optional. Copy `example_config.yaml` and edit as needed:

```yaml
code:
  font_size: 14           # font size for code images
  theme: "monokai"        # any Pygments style: monokai, dracula, vs, solarized-dark, …
  line_numbers: true      # show line numbers
  font: "DejaVu Sans Mono"

latex:
  font_size: 16           # font size for LaTeX images
  dpi: 150                # image resolution
  color: "black"
  background: "white"
  padding: 0.15           # whitespace around each expression (inches)
  try_usetex: true        # use a full LaTeX install when available; falls back to mathtext
```

Pass it with `-c`:

```bash
nb2wb notebook.ipynb -c config.yaml
```

### LaTeX rendering modes

| Mode | Requirement | Quality |
|---|---|---|
| `usetex: true` (default) | LaTeX + dvipng installed | Full LaTeX, best quality |
| mathtext fallback | None (matplotlib built-in) | Most standard expressions |

If `try_usetex: true` and a LaTeX installation is found, full LaTeX is used
automatically. Otherwise `nb2wb` falls back to matplotlib's mathtext, which
handles most common expressions without any extra dependencies.

### Cell tags

Attach tags to cells to control what appears in the output.
In JupyterLab open **View → Cell Toolbar → Tags**; in Jupyter Notebook use
**View → Cell Toolbar → Tags** or edit the cell metadata directly.

| Tag | Effect |
|---|---|
| `hide-cell` | Entire cell omitted (input + output) |
| `hide-input` | Source code hidden; output shown |
| `hide-output` | Output hidden; source code shown |
| `latex-preamble` | Cell source used as LaTeX preamble; cell itself is hidden |

`hide-cell` also works on Markdown cells.

### LaTeX preamble

Custom LaTeX packages and macros can be supplied in two ways (both are
combined when rendering):

**1. Notebook cell (recommended for per-notebook customisation)**

Tag any Markdown cell with `latex-preamble`. Its raw source is injected into
every formula's LaTeX document. The cell is invisible in the output.

```
\usepackage{xcolor}
\definecolor{accent}{HTML}{E8C547}
```

**2. Config file (for project-wide defaults)**

```yaml
latex:
  preamble: |
    \usepackage{xcolor}
    \definecolor{accent}{HTML}{E8C547}
```

> The preamble is only used when `try_usetex: true` and a LaTeX installation
> is found. The mathtext fallback ignores it.

---

### Code themes

Any [Pygments style](https://pygments.org/styles/) works:

```bash
python -c "from pygments.styles import get_all_styles; print(list(get_all_styles()))"
```

Popular choices: `monokai`, `dracula`, `nord`, `solarized-dark`, `vs`,
`github-dark`, `one-dark`.

---

## How it works

```
notebook.ipynb
      │
      ▼
  [nbformat]  parse cells
      │
      ├─ Markdown cell
      │      ├─ display math   →  [matplotlib]  →  PNG image
      │      ├─ inline math    →  [unicodeit]   →  Unicode text
      │      └─ prose          →  [markdown]    →  HTML
      │
      └─ Code cell
             ├─ source         →  [PIL + Pygments]  →  PNG image
             └─ outputs
                    ├─ stream / text/plain  →  [PIL]  →  PNG image
                    ├─ image/png            →  embedded as-is
                    └─ image/svg+xml        →  embedded as-is
                                               │
                                               ▼
                                        page.html  (self-contained)
```

All images are base64-encoded and embedded in the HTML file — no external
assets, no server required.

---

## Requirements

### Core (installed automatically)

- Python ≥ 3.9
- [nbformat](https://nbformat.readthedocs.io/) — notebook parsing
- [nbconvert](https://nbconvert.readthedocs.io/) + [ipykernel](https://ipykernel.readthedocs.io/) — `.qmd` cell execution
- [matplotlib](https://matplotlib.org/) — LaTeX / mathtext rendering
- [Pillow](https://pillow.readthedocs.io/) — image compositing
- [Pygments](https://pygments.org/) — syntax highlighting
- [PyYAML](https://pyyaml.org/) — config and `.qmd` front matter parsing
- [Markdown](https://python-markdown.github.io/) — prose conversion
- [unicodeit](https://github.com/svenkreiss/unicodeit) — inline LaTeX → Unicode

### Optional

| Extra | Install | What it adds |
|---|---|---|
| `examples` | `pip install -e ".[examples]"` | NumPy — required by the bundled example notebooks |
| `dev` | `pip install -e ".[dev]"` | pytest, black, isort |

For the best LaTeX rendering, also install a LaTeX distribution
([TeX Live](https://tug.org/texlive/) or [MiKTeX](https://miktex.org/)) plus
`dvipng`.

---

## License

MIT
