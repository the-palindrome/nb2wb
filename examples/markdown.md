# From Markdown to Web

```latex-preamble
\usepackage{amsmath}
\usepackage{xcolor}
\definecolor{maizeCrayola}{HTML}{E8C547}
\definecolor{blueGray}{HTML}{6290C3}
```

This document demonstrates the `nb2wb` converter with a plain Markdown source
file. It covers the three pillars of technical writing: prose, mathematics, and
code.

Here's a nice image for illustration.

![The parallelogram rule](image.png)

## 1  Inline LaTeX → Unicode

Inline expressions like $\alpha + \beta = \gamma$ or $E = mc^2$ are converted
to Unicode so they render as plain readable text in Substack's editor.

Other examples: the golden ratio $\phi = \frac{1+\sqrt{5}}{2}$, and Euler's
identity $e^{i\pi} + 1 = 0$.

## 2  Display Math → Image

Block equations are rendered to crisp PNG images.

The quadratic formula:

```latex text-snippet
x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a} \label{eq:quadratic}
```

is rendered to

$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a} \label{eq:quadratic}$$

You can render the equation references as `\\eqref{eq:quadratic}`, which renders like this: \eqref{eq:quadratic} gives both roots of $ax^2 + bx + c = 0$ simultaneously.

You can also use colors that are defined in the preamble. Bayes' theorem:

```latex text-snippet
P({\color{maizeCrayola} A} \mid {\color{blueGray} B}) = \frac{P({\color{blueGray} B} \mid {\color{maizeCrayola} A})\, P({\color{maizeCrayola} A})}{P({\color{blueGray} B})} \label{eq:bayes}
```

is rendered to

$$P({\color{maizeCrayola} A} \mid {\color{blueGray} B}) = \frac{P({\color{blueGray} B} \mid {\color{maizeCrayola} A})\, P({\color{maizeCrayola} A})}{P({\color{blueGray} B})} \label{eq:bayes}$$

A matrix equation:

```latex text-snippet
\mathbf{y} = \mathbf{X}\boldsymbol{\beta} + \boldsymbol{\varepsilon} \label{eq:mtx}
```

is rendered to

$$
  \mathbf{y} = \mathbf{X}\boldsymbol{\beta} + \boldsymbol{\varepsilon} \label{eq:mtx}
$$

The Basel formula:

```latex text-snippet
\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}
```

is rendered to

$$
\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}
$$

Now, a complex multi-line example. The Gaussian integral, derived by switching to polar coordinates:

```latex text-snippet
\begin{align*}
I   &= \int_{-\infty}^{\infty} e^{-x^2}\,dx \\[4pt]
I^2 &= \int_{-\infty}^{\infty}\!\int_{-\infty}^{\infty} e^{-(x^2+y^2)}\,dx\,dy \\[4pt]
    &= \int_0^{2\pi}\!\int_0^{\infty} e^{-r^2}\,r\,dr\,d\theta \\[4pt]
    &= 2\pi \cdot \Bigl[-\tfrac{1}{2}e^{-r^2}\Bigr]_0^{\infty} \\[4pt]
    &= \pi \\[4pt]
\therefore\quad I &= \sqrt{\pi}
\end{align*}
```

is rendered to

$$
\begin{align*}
I   &= \int_{-\infty}^{\infty} e^{-x^2}\,dx \\[4pt]
I^2 &= \int_{-\infty}^{\infty}\!\int_{-\infty}^{\infty} e^{-(x^2+y^2)}\,dx\,dy \\[4pt]
    &= \int_0^{2\pi}\!\int_0^{\infty} e^{-r^2}\,r\,dr\,d\theta \\[4pt]
    &= 2\pi \cdot \Bigl[-\tfrac{1}{2}e^{-r^2}\Bigr]_0^{\infty} \\[4pt]
    &= \pi \\[4pt]
\therefore\quad I &= \sqrt{\pi}
\end{align*}
$$

## 3  Code Blocks → Image

Code cells and their outputs are rendered as syntax-highlighted images,
so formatting and colours are perfectly preserved.

```python
def fibonacci(n):
    """Yield the first n Fibonacci numbers."""
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b

print("Fibonacci sequence (first 10 terms):")
print(*fibonacci(10))
```

```python
# Simple list comprehension
x = list(range(10))
[i ** 2 for i in x]
```

## 4  Mixed: equation in context

The softmax function maps a vector $\mathbf{z} \in \mathbb{R}^K$ to a
probability distribution:

$$\sigma(\mathbf{z})_j = \frac{e^{z_j}}{\sum_{k=1}^{K} e^{z_k}}$$

Here $j = 1, \ldots, K$ indexes the classes.  Note that $\sum_j \sigma_j = 1$
by construction.

```python
import math

def softmax(z):
    """Compute softmax values for a list of numbers."""
    z_max = max(z)
    e = [math.exp(x - z_max) for x in z]  # numerical stability
    e_sum = sum(e)
    return [x / e_sum for x in e]

z = [1.0, 2.0, 3.0]
probs = softmax(z)
print(f"softmax({z}) = [{probs[0]:.4f} {probs[1]:.4f} {probs[2]:.4f}]")
```

## 5  Figures

```python
import matplotlib.pyplot as plt


with plt.style.context("seaborn-v0_8-white"):
    x_min = -0.1
    x_max = 20.1
    fig = plt.figure(figsize=(19.2/2, 10.8/2))

    # Generate points using list comprehension
    X = [x / 50.0 - 1 for x in range(101)]  # 101 points from -1 to 1
    y = [x**2 for x in X]
    plt.plot(X, y, color="red")

    plt.tight_layout()
    plt.show()
```
