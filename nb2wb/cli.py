import argparse
import base64
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

from .converter import Converter
from .config import load_config, apply_platform_defaults
from .platforms import get_builder, list_platforms, MIME_TO_EXT

_MIME_TO_EXT = MIME_TO_EXT


def _extract_images(html: str, images_dir: Path) -> str:
    """Replace data-URI ``<img>`` sources with files in *images_dir*.

    Creates *images_dir* if needed, writes each image as a file, and returns
    the HTML with ``src`` attributes rewritten to relative paths
    (e.g. ``images/img_1.png``).
    """
    images_dir.mkdir(parents=True, exist_ok=True)
    counter = [0]

    data_uri_re = re.compile(
        r'<img\s+[^>]*src="(data:([^;]+);base64,([^"]+))"[^>]*/?>',
        re.IGNORECASE,
    )

    def _replace(m: re.Match) -> str:
        counter[0] += 1
        full_tag = m.group(0)
        full_uri = m.group(1)
        mime = m.group(2)
        b64 = m.group(3)

        if mime not in _MIME_TO_EXT:
            return full_tag  # skip non-image MIME types

        ext = _MIME_TO_EXT[mime]
        filename = f"img_{counter[0]}{ext}"
        filepath = images_dir / filename

        filepath.write_bytes(base64.b64decode(b64))

        rel_path = f"images/{filename}"
        return full_tag.replace(f'src="{full_uri}"', f'src="{rel_path}"')

    return data_uri_re.sub(_replace, html)


def _find_free_port() -> int:
    """Return a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get_ngrok_url(max_attempts: int = 10) -> str:
    """Poll ngrok's local API until the public tunnel URL is available."""
    import urllib.request

    for _ in range(max_attempts):
        time.sleep(1)
        try:
            with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels") as resp:
                data = json.loads(resp.read())
            for tunnel in data.get("tunnels", []):
                if tunnel.get("proto") == "https":
                    return tunnel["public_url"]
            if data.get("tunnels"):
                return data["tunnels"][0]["public_url"]
        except Exception:
            continue
    raise RuntimeError("Could not get ngrok tunnel URL. Is ngrok running?")


def _serve(serve_dir: Path, html_name: str) -> None:
    """Extract images, start HTTP server + ngrok tunnel, open browser."""
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
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start a local server with an ngrok tunnel (images get public URLs)",
    )

    args = parser.parse_args()

    if not args.notebook.exists():
        print(f"Error: '{args.notebook}' not found.", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)
    config = apply_platform_defaults(config, args.target)
    builder = get_builder(args.target)
    output_path = args.output or args.notebook.with_suffix(".html")

    print(f"Converting '{args.notebook}' for {builder.name} …")
    try:
        content_html = Converter(config).convert(args.notebook)
        html = builder.build_page(content_html)
    except Exception as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.serve:
        images_dir = output_path.parent / "images"
        html = _extract_images(html, images_dir)
        output_path.write_text(html, encoding="utf-8")
        print(f"Written → {output_path}")
        _serve(output_path.parent, output_path.name)
    else:
        output_path.write_text(html, encoding="utf-8")
        print(f"Written → {output_path}")

        if args.open:
            webbrowser.open(output_path.absolute().as_uri())


if __name__ == "__main__":
    main()
