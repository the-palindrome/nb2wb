---
title: "Publishing a Technical Memo from Markdown"
language: python
---

# Publishing a Technical Memo from Markdown

This example shows how far the Markdown path can go before you ever touch a notebook file. It covers front matter, figures, tables, math, directive comments, fence tags, and execute-time rich outputs.

```latex-preamble
\usepackage{amsmath}
\usepackage{xcolor}
\definecolor{maizeCrayola}{HTML}{E8C547}
\definecolor{blueGray}{HTML}{6290C3}
```

![The parallelogram rule](image.png)

## Inline Math That Stays Readable

Inline expressions such as $\alpha + \beta = \gamma$ and $E = mc^2$ are converted to readable Unicode-oriented text. This keeps the final article approachable in editors that do not support MathJax.

The golden ratio still reads naturally in prose: $\phi = \frac{1 + \sqrt{5}}{2}$.

## Display Math With Labels and References

`nb2wb` keeps equation numbering consistent across the document.

```latex text-snippet
x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a} \label{eq:quadratic}
```

$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a} \label{eq:quadratic}$$

Equation \eqref{eq:quadratic} gives both roots of $ax^2 + bx + c = 0$.

Color definitions from the preamble also work:

```latex text-snippet
P({\color{maizeCrayola} A} \mid {\color{blueGray} B}) =
\frac{P({\color{blueGray} B} \mid {\color{maizeCrayola} A}) P({\color{maizeCrayola} A})}
{P({\color{blueGray} B})}
```

$$
P({\color{maizeCrayola} A} \mid {\color{blueGray} B}) =
\frac{P({\color{blueGray} B} \mid {\color{maizeCrayola} A}) P({\color{maizeCrayola} A})}
{P({\color{blueGray} B})}
$$

## Tables and Lists Survive the Trip

The Markdown reader keeps ordinary prose structure, including lists and tables.

- Draft in plain Markdown.
- Add math only where it helps.
- Use code fences when the article needs executable examples.

| Target | Typical image mode | Good first choice |
| --- | --- | --- |
| `substack` | embed | long-form essays |
| `medium` | copyable | publication workflows |
| `x` | copyable | short technical posts |

## Execute-Time Code and Output

Run this file with `--execute` when you want fresh code outputs to appear in the final HTML.

```python
def fibonacci(n):
    """Yield the first n Fibonacci numbers."""
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b


print("First ten Fibonacci numbers:")
print(*fibonacci(10))
```

```python
from IPython.display import HTML, SVG, display

display(HTML(
    "<div style='padding:0.75rem;border:1px solid #dbe4ee;border-radius:12px;'>"
    "<strong>Rich HTML output</strong> also makes the trip."
    "</div>"
))

display(SVG(
    "<svg xmlns='http://www.w3.org/2000/svg' width='220' height='70'>"
    "<rect width='220' height='70' rx='12' fill='#e0f2fe' />"
    "<text x='16' y='43' font-size='24' fill='#0369a1'>SVG output</text>"
    "</svg>"
))
```

```python
import sys

print("Use --warnings to render this stderr message.", file=sys.stderr)
```

## Visibility Controls

Markdown directives apply to the next fenced code block. This makes it easy to keep the article narrative close to the example it controls.

<!-- nb2wb: hide-input -->
```python
print("Only the output should be visible when you add --execute.")
```

```python hide-output
print("The source is visible, but this output is intentionally hidden.")
```

<!-- nb2wb: hide-cell -->
```python
print("This block is a drafting aid and does not belong in the final article.")
```

<!-- nb2wb: text-snippet -->
```bash
pip install nb2wb
nb2wb examples/markdown.md --execute --warnings -t medium
```

## Figures in Context

You can mix explanatory prose, equations, and plotting code in one article-sized source file.

```python
import matplotlib.pyplot as plt

with plt.style.context("seaborn-v0_8-white"):
    x = [value / 20 for value in range(-20, 21)]
    y = [value ** 2 for value in x]
    fig = plt.figure(figsize=(8, 4.5))
    plt.plot(x, y, color="#ef4444", linewidth=3)
    plt.title("A simple parabola")
    plt.tight_layout()
    plt.show()
```
