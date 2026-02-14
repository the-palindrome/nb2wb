import argparse
import sys
import webbrowser
from pathlib import Path

from .converter import Converter
from .config import load_config
from .platforms import get_builder, list_platforms


def main() -> None:
    platforms = list_platforms()
    parser = argparse.ArgumentParser(
        prog="nb2wb",
        description="Convert Jupyter Notebooks or Quarto documents to web-ready HTML",
    )
    parser.add_argument("notebook", type=Path, help="Path to the .ipynb or .qmd file")
    parser.add_argument(
        "-c", "--config", type=Path, default=None, help="Path to config.yaml (optional)"
    )
    parser.add_argument(
        "-t",
        "--target",
        type=str,
        choices=platforms,
        default="substack",
        help=f"Target platform (choices: {', '.join(platforms)}; default: substack)",
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
    builder = get_builder(args.target)
    output_path = args.output or args.notebook.with_suffix(".html")

    print(f"Converting '{args.notebook}' for {builder.name} …")
    try:
        content_html = Converter(config).convert(args.notebook)
        html = builder.build_page(content_html)
    except Exception as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        sys.exit(1)

    output_path.write_text(html, encoding="utf-8")
    print(f"Written → {output_path}")

    if args.open:
        webbrowser.open(output_path.absolute().as_uri())


if __name__ == "__main__":
    main()
