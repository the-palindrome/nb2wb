# nb2wb

**Write in Jupyter Notebooks. Publish on Substack.**

`nb2wb` converts a Jupyter Notebook into a self-contained HTML file you can
paste directly into a Substack draft — with LaTeX, code, and outputs all
rendered faithfully.

---

## Why

Substack's editor strips MathJax and code-block formatting. `nb2wb` sidesteps
this by turning the parts Substack can't handle into **images**, and converting
simple inline math into **Unicode text** that pastes cleanly as prose.

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
pip install -r requirements.txt
pip install -e .
```

---

## Usage

```bash
nb2wb notebook.ipynb                         # → notebook.html
nb2wb notebook.ipynb -c config.yaml          # with custom config
nb2wb notebook.ipynb -o out.html             # explicit output path
nb2wb notebook.ipynb --open                  # open in browser when done
```

Then open the HTML file in your browser, click **Copy to clipboard**, and
paste into your Substack draft.

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

- Python ≥ 3.9
- [Pillow](https://pillow.readthedocs.io/) — image rendering
- [Pygments](https://pygments.org/) — syntax highlighting
- [matplotlib](https://matplotlib.org/) — LaTeX / mathtext rendering
- [nbformat](https://nbformat.readthedocs.io/) — notebook parsing
- [unicodeit](https://github.com/svenkreiss/unicodeit) — inline LaTeX → Unicode
- [Markdown](https://python-markdown.github.io/) — prose conversion
- [PyYAML](https://pyyaml.org/) — config file parsing

For the best LaTeX rendering, also install a LaTeX distribution
([TeX Live](https://tug.org/texlive/) or [MiKTeX](https://miktex.org/)) plus
`dvipng`.

---

## License

MIT
