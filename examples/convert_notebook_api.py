import os
import sys
from pathlib import Path

# Allow running this script directly from a source checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import nb2wb


def main() -> None:
    examples_dir = Path(__file__).resolve().parent
    input_path = examples_dir / "notebook.ipynb"
    config_path = examples_dir / "config.yaml"
    output_path = examples_dir / "notebook_api.html"

    previous_cwd = Path.cwd()
    try:
        os.chdir(examples_dir)
        payload = nb2wb.load_input_payload(input_path)
        html = nb2wb.convert(
            payload,
            config=config_path,
            target="substack",
            working_dir=examples_dir,
        )
    finally:
        os.chdir(previous_cwd)

    output_path.write_text(html, encoding="utf-8")
    print(f"Saved HTML to {output_path}")


if __name__ == "__main__":
    main()
