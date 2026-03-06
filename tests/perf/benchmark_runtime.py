"""Lightweight runtime benchmark scenarios for manual regression tracking.

Usage:
    MPLCONFIGDIR=/tmp/matplotlib-cache python3 tests/perf/benchmark_runtime.py
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

import nbformat

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nb2wb.api import convert


def _scenario_code_heavy() -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook()
    for i in range(120):
        cell = nbformat.v4.new_code_cell(f"x={i}\nprint(x*2)")
        cell["execution_count"] = i + 1
        cell["outputs"] = [
            nbformat.from_dict(
                {
                    "output_type": "stream",
                    "name": "stdout",
                    "text": f"{i * 2}\n",
                }
            )
        ]
        nb.cells.append(cell)
    return nb


def _scenario_markdown_tiny() -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook()
    for i in range(1000):
        nb.cells.append(nbformat.v4.new_markdown_cell(f"Tiny **cell** {i} with `x`"))
    return nb


def _scenario_math_repeated() -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook()
    math = "$$\\int_0^1 x^2 dx = \\frac{1}{3}$$\n"
    for _ in range(60):
        nb.cells.append(nbformat.v4.new_markdown_cell(math * 6))
    return nb


def _run(name: str, notebook: nbformat.NotebookNode, runs: int = 3) -> dict[str, float]:
    timings: list[float] = []
    for _ in range(runs):
        start = time.perf_counter()
        convert(
            notebook,
            target="substack",
            config={"latex": {"try_usetex": False}},
            raw_mode=False,
        )
        timings.append(time.perf_counter() - start)
    return {
        "min_s": round(min(timings), 3),
        "mean_s": round(sum(timings) / len(timings), 3),
        "max_s": round(max(timings), 3),
    }


def main() -> None:
    scenarios = {
        "code_heavy": _scenario_code_heavy(),
        "markdown_tiny": _scenario_markdown_tiny(),
        "math_repeated": _scenario_math_repeated(),
    }
    report = {name: _run(name, notebook) for name, notebook in scenarios.items()}
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
