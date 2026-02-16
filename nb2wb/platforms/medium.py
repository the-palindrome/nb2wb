"""
Medium platform HTML builder.

Medium's editor strips data-URI images from pasted HTML but fetches images at
real HTTP URLs.  The default output includes per-image "Copy image" hover
buttons so users can paste images individually.  When combined with the CLI's
``--serve`` flag (ngrok tunnel), images get public URLs and one-click copy
works out of the box.
"""
from __future__ import annotations

import re
from .base import PlatformBuilder

# ---- HTML template --------------------------------------------------------

_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>nb2wb — Medium Preview</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: charter, Georgia, Cambria, "Times New Roman", Times, serif;
      font-size: 20px;
      line-height: 1.8;
      color: #242424;
      max-width: 700px;
      margin: 0 auto;
      padding: 24px 20px 60px;
      background: #fff;
    }
    #toolbar {
      position: sticky;
      top: 0;
      z-index: 100;
      background: #1a8917;
      color: #fff;
      padding: 10px 20px;
      border-radius: 8px;
      margin-bottom: 28px;
      display: flex;
      align-items: center;
      gap: 16px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    #toolbar button {
      background: #fff;
      color: #1a8917;
      border: none;
      padding: 8px 18px;
      font-size: 14px;
      font-weight: 600;
      border-radius: 20px;
      cursor: pointer;
      transition: background 0.15s;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    #toolbar button:hover { background: #e6f4e6; }
    #toolbar p { margin: 0; font-size: 13px; opacity: 0.9; }
    #content {
      background: #fff;
    }
    /* Image containers with inline copy buttons */
    .image-container {
      position: relative;
      margin: 0.5em 0;
    }
    .image-container img {
      max-width: 100%;
      height: auto;
      display: block;
      border-radius: 5px;
    }
    .copy-image-btn {
      position: absolute;
      top: 8px;
      right: 8px;
      background: rgba(26, 137, 23, 0.9);
      color: #fff;
      border: none;
      padding: 6px 14px;
      font-size: 13px;
      font-weight: 600;
      border-radius: 16px;
      cursor: pointer;
      opacity: 0;
      transition: opacity 0.2s;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .image-container:hover .copy-image-btn { opacity: 1; }
    .copy-image-btn:hover { background: rgba(13, 95, 11, 0.95); }
    .copy-image-btn.copied { opacity: 1; background: #0d5f0b; }
    /* --- cell wrappers --- */
    .md-cell { margin-bottom: 1.4em; }
    .code-cell { margin: 1.6em 0; }
    /* --- images --- */
    img {
      max-width: 100%;
      height: auto;
      display: block;
    }
    .code-cell img { border-radius: 5px; }
    /* --- markdown typography --- */
    h1, h2, h3, h4, h5, h6 {
      font-family: sohne, "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-weight: 700;
      margin: 1.6em 0 0.4em;
      line-height: 1.3;
      color: #242424;
    }
    h1 { font-size: 2em; }
    h2 { font-size: 1.6em; }
    h3 { font-size: 1.3em; letter-spacing: -0.02em; }
    p { margin: 0 0 1.1em; }
    ul, ol { margin: 0 0 1.1em; padding-left: 1.8em; }
    li { margin-bottom: 0.3em; }
    blockquote {
      border-left: 3px solid #242424;
      margin: 1.2em 0;
      padding: 0.1em 1.2em;
      color: #242424;
      font-style: italic;
    }
    pre, code {
      font-family: Menlo, Monaco, "Courier New", Courier, monospace;
      font-size: 0.85em;
    }
    pre {
      background: #f2f2f2;
      padding: 1.2em;
      border-radius: 4px;
      overflow-x: auto;
    }
    code {
      background: #f2f2f2;
      padding: 0.15em 0.4em;
      border-radius: 3px;
    }
    pre code {
      background: none;
      padding: 0;
    }
    table { border-collapse: collapse; width: 100%; margin-bottom: 1.2em; }
    th, td { border: 1px solid #e0e0e0; padding: 0.5em 0.8em; }
    th { background: #f9f9f9; font-weight: 600; }
    hr { border: none; border-top: 1px solid #e0e0e0; margin: 2em 0; }
    a { color: inherit; text-decoration: underline; }
    .nb2wb-footer {
      margin-top: 3em;
      padding-top: 1em;
      border-top: 1px solid #e6e6e6;
      text-align: center;
      font-size: 0.8em;
      color: #999;
    }
    .nb2wb-footer a { color: #999; text-decoration: none; }
    .nb2wb-footer a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div id="toolbar">
    <button id="copy-btn" onclick="copyContent()">&#128203; Copy to clipboard</button>
    <p>Paste into Medium. If images are missing, hover each one to copy it.</p>
  </div>
  <div id="content">
"""

_TAIL = """\
  <div class="nb2wb-footer">
    Made with <a href="https://github.com/the-palindrome/nb2wb">nb2wb</a>
  </div>
  </div><!-- #content -->

  <script>
    async function copyContent() {
      var btn = document.getElementById("copy-btn");
      try {
        var content = document.getElementById("content").cloneNode(true);

        // Unwrap .md-cell and .code-cell divs to avoid empty lines in Medium
        content.querySelectorAll(".md-cell, .code-cell").forEach(function(div) {
          var parent = div.parentNode;
          while (div.firstChild) {
            parent.insertBefore(div.firstChild, div);
          }
          parent.removeChild(div);
        });

        // Unwrap image containers but keep the <img> tags
        content.querySelectorAll(".image-container").forEach(function(container) {
          var img = container.querySelector("img");
          if (img) {
            container.replaceWith(img);
          }
        });

        // Remove footer
        var footer = content.querySelector(".nb2wb-footer");
        if (footer) footer.remove();

        var html = content.innerHTML;
        var blob = new Blob([html], { type: "text/html" });
        var item = new ClipboardItem({ "text/html": blob });
        await navigator.clipboard.write([item]);

        btn.textContent = "\\u2713 Copied!";
        setTimeout(function() { btn.textContent = "\\u{1F4CB} Copy to clipboard"; }, 2500);
      } catch (_) {
        var el = document.getElementById("content");
        var range = document.createRange();
        range.selectNode(el);
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        document.execCommand("copy");
        window.getSelection().removeAllRanges();
        btn.textContent = "\\u2713 Copied!";
        setTimeout(function() { btn.textContent = "\\u{1F4CB} Copy to clipboard"; }, 2500);
      }
    }

    // Copy a single image to clipboard
    async function copyImage(imgSrc, button) {
      try {
        var blob;
        if (imgSrc.startsWith("data:")) {
          var base64Data = imgSrc.split(",")[1];
          var mimeType = imgSrc.match(/data:([^;]+);/)[1];
          var byteChars = atob(base64Data);
          var bytes = new Uint8Array(byteChars.length);
          for (var i = 0; i < byteChars.length; i++) {
            bytes[i] = byteChars.charCodeAt(i);
          }
          blob = new Blob([bytes], { type: mimeType });
        } else {
          button.textContent = "Fetching\\u2026";
          var response = await fetch(imgSrc);
          blob = await response.blob();
        }

        await navigator.clipboard.write([
          new ClipboardItem({ [blob.type]: blob })
        ]);

        button.textContent = "\\u2713 Copied";
        button.classList.add("copied");
        setTimeout(function() {
          button.textContent = "Copy image";
          button.classList.remove("copied");
        }, 3000);
      } catch (err) {
        console.error("Failed to copy image:", err);
        button.textContent = "Failed";
        setTimeout(function() { button.textContent = "Copy image"; }, 3000);
      }
    }

    // Wire up copy-image buttons
    document.addEventListener("DOMContentLoaded", function() {
      document.querySelectorAll(".image-container").forEach(function(container) {
        var img = container.querySelector("img");
        var btn = container.querySelector(".copy-image-btn");
        if (img && btn) {
          btn.addEventListener("click", function() {
            copyImage(img.src, btn);
          });
        }
      });
    });
  </script>
</body>
</html>
"""

# ---- Mapping from data-URI MIME type to file extension --------------------
_MIME_TO_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
}


class MediumBuilder(PlatformBuilder):
    """
    HTML builder optimized for Medium.

    Wraps each image in a container with a hover "Copy image" button for the
    default (no-serve) workflow.  The main "Copy to clipboard" button copies
    the full content — images transfer automatically when served via ``--serve``
    (public URLs) and are available via per-image buttons otherwise.
    """

    @property
    def name(self) -> str:
        return "Medium"

    def build_page(self, content_html: str) -> str:
        """Wrap content in Medium-optimized HTML page."""
        content_html = self._make_images_copyable(content_html)
        return _HEAD + content_html + _TAIL

    def _make_images_copyable(self, html: str) -> str:
        """Wrap each <img> in a container with an inline copy button."""
        img_pattern = re.compile(
            r'<img\s+[^>]*src="([^"]+)"[^>]*/?>',
            re.IGNORECASE,
        )

        def wrap_image(match: re.Match) -> str:
            img_src = match.group(1)

            if not img_src.startswith("data:"):
                img_src = self._to_data_uri(img_src)

            full_tag = match.group(0)
            alt_match = re.search(r'alt="([^"]*)"', full_tag)
            alt_text = alt_match.group(1) if alt_match else "image"

            return (
                f'<div class="image-container">'
                f'<img src="{img_src}" alt="{alt_text}">'
                f'<button class="copy-image-btn" type="button">Copy image</button>'
                f'</div>'
            )

        return img_pattern.sub(wrap_image, html)

    # _to_data_uri inherited from PlatformBuilder
