import argparse
import base64
import binascii
import functools
import json
import re
import socket
import subprocess
import sys
import time
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from ._path_utils import sanitize_optional_cli_path
from .api import convert as convert_notebook
from .api import load_input_payload
from .platforms import list_platforms, MIME_TO_EXT

_ALLOWED_INPUT_SUFFIXES = frozenset({".ipynb", ".qmd", ".md"})


def _positive_int(value: str) -> int:
    """Parse a CLI argument and reject non-positive integers.

    Args:
        value: Raw command-line string value to validate.

    Returns:
        The parsed positive integer.
    """
    out = int(value)
    if out <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return out


def _extract_images(html: str, images_dir: Path) -> str:
    """Replace data-URI ``<img>`` sources with files in *images_dir*.

    Creates *images_dir* if needed, writes each image as a file, and returns
    the HTML with ``src`` attributes rewritten to relative paths
    (e.g. ``images/img_1.png``).

    Args:
        html: HTML document whose embedded images should be extracted.
        images_dir: Directory where extracted image files will be written.

    Returns:
        HTML with matching data-URI image sources rewritten to file paths.
    """
    images_dir.mkdir(parents=True, exist_ok=True)
    counter = 0

    data_uri_re = re.compile(
        r'<img\s+[^>]*src="(data:([^;]+);base64,([^"]+))"[^>]*/?>',
        re.IGNORECASE,
    )

    def _replace(m: re.Match) -> str:
        """Persist one embedded image and rewrite its ``src`` attribute.

        Args:
            m: Regex match containing the full tag, MIME type, and payload.

        Returns:
            Updated HTML for the image tag, or the original tag on failure.
        """
        nonlocal counter
        counter += 1
        full_tag = m.group(0)
        full_uri = m.group(1)
        mime = m.group(2)
        b64 = m.group(3)

        if mime not in MIME_TO_EXT:
            return full_tag  # skip non-image MIME types

        ext = MIME_TO_EXT[mime]
        filename = f"img_{counter}{ext}"
        filepath = images_dir / filename

        try:
            filepath.write_bytes(base64.b64decode(b64, validate=True))
        except (binascii.Error, ValueError):
            # Malformed payload: keep the original tag unchanged.
            counter -= 1
            return full_tag

        rel_path = f"images/{filename}"
        return full_tag.replace(f'src="{full_uri}"', f'src="{rel_path}"')

    return data_uri_re.sub(_replace, html)


def _find_free_port() -> int:
    """Return a free TCP port on localhost.

    Args:
        None.

    Returns:
        An available TCP port number bound on the loopback interface.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get_ngrok_url(max_attempts: int = 10) -> str:
    """Poll ngrok's local API until the public tunnel URL is available.

    Args:
        max_attempts: Maximum number of polling attempts before failing.

    Returns:
        The public ngrok URL for the active HTTP tunnel.
    """
    import urllib.error
    import urllib.request

    for _ in range(max_attempts):
        time.sleep(1)
        try:
            with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=2) as resp:
                data = json.loads(resp.read())
            for tunnel in data.get("tunnels", []):
                if tunnel.get("proto") == "https":
                    return tunnel["public_url"]
            if data.get("tunnels"):
                return data["tunnels"][0]["public_url"]
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, TypeError):
            continue
    raise RuntimeError("Could not get ngrok tunnel URL. Is ngrok running?")


def _serve(serve_dir: Path, html_name: str) -> None:
    """Serve a generated HTML page locally and through ngrok.

    Args:
        serve_dir: Directory containing the page and extracted assets.
        html_name: Filename of the HTML page to open and serve.

    Returns:
        ``None``. The function blocks until the server is interrupted.
    """
    port = _find_free_port()
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(serve_dir))
    server = HTTPServer(("127.0.0.1", port), handler)

    # Start ngrok
    try:
        ngrok_proc = subprocess.Popen(
            ["ngrok", "http", str(port), "--log=stderr"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        server.server_close()
        print(
            "Error: 'ngrok' not found.\n"
            "Install it from https://ngrok.com/download and run 'ngrok config add-authtoken <TOKEN>'.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        public_url = _get_ngrok_url()
    except RuntimeError as exc:
        ngrok_proc.terminate()
        server.server_close()
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    page_url = f"{public_url}/{html_name}"
    print(f"Serving at {page_url}")
    print("Copy your article, then press Ctrl-C to stop.")
    webbrowser.open(page_url)

    # Serve until interrupted
    import threading

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        ngrok_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        ngrok_proc.terminate()
        ngrok_proc.wait()
        print("\nServer stopped.")


def main() -> None:
    """Run the ``nb2wb`` command-line entry point.

    Args:
        None.

    Returns:
        ``None``. The function writes output files or exits on error.
    """
    platforms = list_platforms()
    parser = argparse.ArgumentParser(
        prog="nb2wb",
        description="Convert Jupyter Notebooks, Quarto, or Markdown documents to web-ready HTML",
    )
    parser.add_argument("notebook", type=Path, help="Path to the .ipynb, .qmd, or .md file")
    parser.add_argument(
        "-c", "--config", type=Path, default=None, help="Path to config.yaml (optional)"
    )
    parser.add_argument(
        "-t",
        "--target",
        type=str,
        choices=platforms,
        default="default",
        help=f"Target platform (choices: {', '.join(platforms)}; default: default)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output HTML file path (default: <notebook>.html)",
    )
    parser.add_argument(
        "--image-strategy",
        type=str,
        choices=["embed", "copyable"],
        default=None,
        help="Override image handling strategy for normal mode.",
    )
    parser.add_argument(
        "--raw-image-strategy",
        type=str,
        choices=["embed", "copyable", "preserve"],
        default=None,
        help="Override image handling strategy for --raw output.",
    )
    parser.add_argument(
        "--copy-script",
        type=str,
        choices=["simple", "copyable", "none"],
        default=None,
        help="Override preview copy-script mode in non-raw output.",
    )
    parser.add_argument(
        "--article-width",
        type=_positive_int,
        default=None,
        help="Override article max width in pixels for preview wrapper.",
    )
    parser.add_argument(
        "--table-mode",
        type=str,
        choices=["native", "image"],
        default=None,
        help="Override table rendering mode before wrapping output.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the output HTML in the browser when done",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start a local server with an ngrok tunnel (images get public URLs)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute code blocks via Jupyter kernel before rendering (.ipynb, .qmd, .md).",
    )
    parser.add_argument(
        "--warnings",
        action="store_true",
        help="Render stderr warning/log outputs from code cells.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Emit raw article HTML without the preview toolbar/header.",
    )

    args = parser.parse_args()

    try:
        notebook_path = _sanitize_cli_path(
            args.notebook,
            arg_name="notebook path",
            must_exist=True,
            allowed_suffixes=_ALLOWED_INPUT_SUFFIXES,
        )
        config_path = _sanitize_cli_path(args.config, arg_name="config path")
        output_path = _sanitize_cli_path(
            args.output or notebook_path.with_suffix(".html"),
            arg_name="output path",
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.target == "default":
        print(f"Converting '{notebook_path}' using default mode …")
    else:
        print(f"Converting '{notebook_path}' for {args.target} …")
    try:
        payload = load_input_payload(notebook_path)
        target_options: dict[str, object] = {}
        if args.image_strategy is not None:
            target_options["image_strategy"] = args.image_strategy
        if args.raw_image_strategy is not None:
            target_options["raw_image_strategy"] = args.raw_image_strategy
        if args.copy_script is not None:
            target_options["copy_script_mode"] = args.copy_script
        if args.article_width is not None:
            target_options["article_width_px"] = args.article_width
        if args.table_mode is not None:
            target_options["table_mode"] = args.table_mode

        html = convert_notebook(
            payload,
            config=config_path,
            target=args.target,
            target_options=target_options or None,
            execute=args.execute,
            warnings_mode=args.warnings,
            working_dir=notebook_path.parent,
            raw_mode=args.raw,
        )
    except Exception as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.serve:
        images_dir = output_path.parent / "images"
        html = _extract_images(html, images_dir)

    output_path.write_text(html, encoding="utf-8")
    print(f"Written → {output_path}")

    if args.serve:
        _serve(output_path.parent, output_path.name)
    elif args.open:
        webbrowser.open(output_path.absolute().as_uri())


def _sanitize_cli_path(
    path: Path | None,
    *,
    arg_name: str,
    must_exist: bool = False,
    allowed_suffixes: frozenset[str] | None = None,
) -> Path | None:
    """Validate and sanitize a user-provided filesystem path.

    Args:
        path: Parsed path value, or ``None`` when the argument is omitted.
        arg_name: Human-readable argument label for error messages.
        must_exist: Whether the path must already exist on disk.
        allowed_suffixes: Optional set of permitted filename suffixes.

    Returns:
        The validated path, or ``None`` when no path was provided.
    """
    return sanitize_optional_cli_path(
        path,
        label=arg_name,
        must_exist=must_exist,
        allowed_suffixes=allowed_suffixes,
    )


if __name__ == "__main__":
    main()
