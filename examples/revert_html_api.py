"""Reverse-conversion API example for the bundled HTML sample."""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running this script directly from a source checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import nbformat
import nb2wb


def main() -> None:
    examples_dir = Path(__file__).resolve().parent
    payload = nb2wb.load_html_payload(examples_dir / "reverse_article.html")
    notebook = nb2wb.revert(payload)

    output_path = examples_dir / "reverse_article_api.ipynb"
    with output_path.open("w", encoding="utf-8") as handle:
        nbformat.write(notebook, handle)

    print(f"Wrote scaffolded notebook to {output_path}")


if __name__ == "__main__":
    main()
