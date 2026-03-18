from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
import time

import nbformat

from ._logging import verbose_logging
from ._path_utils import sanitize_optional_cli_path
from .api import load_html_payload, revert
from .ocr.gemini import GeminiOCRPipeline
from .ocr.local import local_ocr_pipeline
from .ocr.openai import OpenAIOCRPipeline

_ALLOWED_INPUT_SUFFIXES = frozenset({".html", ".htm"})
logger = logging.getLogger(__name__)


def main() -> None:
    """Run the ``wb2nb`` command-line entry point.

    Args:
        None.

    Returns:
        ``None``. The function writes output or exits with a CLI error.
    """
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
        choices=("local", "openai", "gemini"),
        default=None,
        help="Optional OCR pipeline for image-based reverse conversion.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model to use when --ocr-pipeline openai or gemini is selected.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose package debug logging to stderr.",
    )
    parser.add_argument(
        "--disallow-remote-image-urls",
        dest="allow_remote_image_urls",
        action="store_false",
        default=True,
        help="Block OpenAI or Gemini OCR from fetching public remote image URLs.",
    )
    args = parser.parse_args()

    if args.ocr_pipeline in {"openai", "gemini"}:
        if not args.model:
            parser.error(
                "--model is required when --ocr-pipeline openai or gemini is selected"
            )
    if args.ocr_pipeline == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            parser.error(
                "OPENAI_API_KEY environment variable is required when "
                "--ocr-pipeline openai is selected"
            )
    if args.ocr_pipeline == "gemini":
        if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
            parser.error(
                "GEMINI_API_KEY or GOOGLE_API_KEY environment variable is required "
                "when --ocr-pipeline gemini is selected"
            )

    with verbose_logging(args.verbose):
        started = time.monotonic()
        try:
            document_path = sanitize_optional_cli_path(
                args.document,
                label="document path",
                must_exist=True,
                allowed_suffixes=_ALLOWED_INPUT_SUFFIXES,
            )
            output_path = sanitize_optional_cli_path(
                args.output or document_path.with_suffix(".ipynb"),
                label="output path",
            )
        except (FileNotFoundError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        try:
            ocr_pipeline = None
            if args.ocr_pipeline == "local":
                ocr_pipeline = local_ocr_pipeline
            elif args.ocr_pipeline == "openai":
                ocr_pipeline = OpenAIOCRPipeline(
                    model=args.model,
                    verbose=args.verbose,
                    allow_remote_image_urls=args.allow_remote_image_urls,
                )
            elif args.ocr_pipeline == "gemini":
                ocr_pipeline = GeminiOCRPipeline(
                    model=args.model,
                    verbose=args.verbose,
                    allow_remote_image_urls=args.allow_remote_image_urls,
                )
        except (RuntimeError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        logger.debug(
            "Reverse CLI starting (ocr_pipeline=%s, model=%s)",
            args.ocr_pipeline,
            args.model,
        )
        print(f"Reverting '{document_path}' into a notebook …")
        try:
            payload = load_html_payload(document_path, verbose=args.verbose)
            notebook = revert(
                payload,
                ocr_pipeline=ocr_pipeline,
                verbose=args.verbose,
            )
        except Exception as exc:
            print(f"Conversion failed: {exc}", file=sys.stderr)
            sys.exit(1)

        with output_path.open("w", encoding="utf-8") as handle:
            nbformat.write(notebook, handle)
        print(f"Written → {output_path}")
        logger.debug(
            "Wrote notebook output to %s in %.2fs",
            output_path,
            time.monotonic() - started,
        )


if __name__ == "__main__":
    main()
