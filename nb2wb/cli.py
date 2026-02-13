import argparse
import sys
import webbrowser
from pathlib import Path

from .converter import Converter
from .config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="nb2wb",
        description="Convert Jupyter Notebooks to Substack-ready HTML",
    )
    parser.add_argument("notebook", type=Path, help="Path to the .ipynb notebook file")
    parser.add_argument(
        "-c", "--config", type=Path, default=None, help="Path to config.yaml (optional)"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output HTML file path (default: <notebook>.html)",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the output HTML in the browser when done",
    )

    args = parser.parse_args()

    if not args.notebook.exists():
        print(f"Error: '{args.notebook}' not found.", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)
    output_path = args.output or args.notebook.with_suffix(".html")

    print(f"Converting '{args.notebook}' …")
    try:
        html = Converter(config).convert(args.notebook)
    except Exception as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        sys.exit(1)

    output_path.write_text(html, encoding="utf-8")
    print(f"Written → {output_path}")

    if args.open:
        webbrowser.open(output_path.absolute().as_uri())


if __name__ == "__main__":
    main()
