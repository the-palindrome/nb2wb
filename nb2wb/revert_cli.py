from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import nbformat

from .api import load_html_payload, revert
from .ocr.local import local_ocr_pipeline
from .ocr.openai import OpenAIOCRPipeline

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_ALLOWED_INPUT_SUFFIXES = frozenset({".html", ".htm"})


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wb2nb",
        description="Convert HTML posts into scaffolded Jupyter notebooks",
    )
    parser.add_argument("document", type=Path, help="Path to the .html or .htm file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output notebook path (default: <document>.ipynb)",
    )
    parser.add_argument(
        "--ocr-pipeline",
        choices=("local", "openai"),
        default=None,
        help="Optional OCR pipeline for image-based reverse conversion.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model to use when --ocr-pipeline openai is selected.",
    )
    args = parser.parse_args()

    if args.ocr_pipeline == "openai":
        if not args.model:
            parser.error(
                "--model is required when --ocr-pipeline openai is selected"
            )
        if not os.getenv("OPENAI_API_KEY"):
            parser.error(
                "OPENAI_API_KEY environment variable is required when "
                "--ocr-pipeline openai is selected"
            )

    try:
        document_path = _sanitize_cli_path(
            args.document,
            arg_name="document path",
            must_exist=True,
            allowed_suffixes=_ALLOWED_INPUT_SUFFIXES,
        )
        output_path = _sanitize_cli_path(
            args.output or document_path.with_suffix(".ipynb"),
            arg_name="output path",
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        ocr_pipeline = None
        if args.ocr_pipeline == "local":
            ocr_pipeline = local_ocr_pipeline
        elif args.ocr_pipeline == "openai":
            ocr_pipeline = OpenAIOCRPipeline(model=args.model)
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Reverting '{document_path}' into a notebook …")
    try:
        payload = load_html_payload(document_path)
        notebook = revert(payload, ocr_pipeline=ocr_pipeline)
    except Exception as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        sys.exit(1)

    with output_path.open("w", encoding="utf-8") as handle:
        nbformat.write(notebook, handle)
    print(f"Written → {output_path}")


def _sanitize_cli_path(
    path: Path | None,
    *,
    arg_name: str,
    must_exist: bool = False,
    allowed_suffixes: frozenset[str] | None = None,
) -> Path | None:
    if path is None:
        return None

    raw = str(path)
    if _CONTROL_CHAR_RE.search(raw):
        raise ValueError(f"{arg_name} contains invalid control characters")

    if allowed_suffixes is not None:
        suffix = path.suffix.lower()
        if suffix not in allowed_suffixes:
            allowed = ", ".join(sorted(allowed_suffixes))
            raise ValueError(f"{arg_name} must use one of: {allowed}")

    if must_exist and not path.exists():
        raise FileNotFoundError(f"'{path}' not found.")

    return path


if __name__ == "__main__":
    main()
