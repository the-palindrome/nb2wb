"""Forward-conversion API example for the bundled notebook sample."""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path

# Allow running this script directly from a source checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import nb2wb


@contextmanager
def _working_directory(path: Path):
    """Temporarily switch the working directory for local asset resolution."""
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def main() -> None:
    examples_dir = Path(__file__).resolve().parent
    payload = nb2wb.load_input_payload(examples_dir / "notebook.ipynb")
    config_path = examples_dir / "config.yaml"

    with _working_directory(examples_dir):
        preview_html = nb2wb.convert(
            payload,
            config=config_path,
            target="substack",
            target_options={"article_width_px": 860},
            working_dir=examples_dir,
        )
        raw_html = nb2wb.convert(
            payload,
            config=config_path,
            target="medium",
            raw_mode=True,
            working_dir=examples_dir,
        )

    preview_path = examples_dir / "notebook_api.html"
    raw_path = examples_dir / "notebook_api_raw.html"
    preview_path.write_text(preview_html, encoding="utf-8")
    raw_path.write_text(raw_html, encoding="utf-8")

    print(f"Wrote preview HTML to {preview_path}")
    print(f"Wrote raw HTML to {raw_path}")


if __name__ == "__main__":
    main()
