"""
X (Twitter) Articles platform HTML builder.

X's editor doesn't support base64 data URIs, but accepts images pasted from clipboard.
This builder creates an interactive HTML with "Copy image" buttons for each image.
"""
from __future__ import annotations

from .base import PlatformBuilder

# X Articles HTML template with interactive image copying
_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>nb2wb — X Articles Preview</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 19px;
      line-height: 1.6;
      color: #0f1419;
      max-width: 680px;
      margin: 0 auto;
      padding: 24px 20px 60px;
      background: #fff;
    }
    #toolbar {
      position: sticky;
      top: 0;
      z-index: 100;
      background: #1d9bf0;
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
      color: #1d9bf0;
      border: none;
      padding: 8px 18px;
      font-size: 14px;
      font-weight: 600;
      border-radius: 20px;
      cursor: pointer;
      transition: background 0.15s;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    #toolbar button:hover { background: #e8f5fe; }
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
      background: rgba(29, 155, 240, 0.9);
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
    .copy-image-btn:hover { background: rgba(20, 120, 190, 0.95); }
    .copy-image-btn.copied { opacity: 1; background: #1478be; }
    /* --- cell wrappers --- */
    .md-cell { margin-bottom: 1.3em; }
    .code-cell { margin: 1.5em 0; }
    /* --- images --- */
    img {
      max-width: 100%;
      height: auto;
      display: block;
    }
    .code-cell img { border-radius: 5px; }
    /* --- markdown typography --- */
    h1, h2, h3, h4, h5, h6 {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-weight: 800;
      margin: 1.5em 0 0.6em;
      line-height: 1.3;
      color: #0f1419;
    }
    h1 { font-size: 2.2em; }
    h2 { font-size: 1.8em; }
    h3 { font-size: 1.4em; }
    p { margin: 0 0 1em; }
    ul, ol { margin: 0 0 1em; padding-left: 1.8em; }
    li { margin-bottom: 0.3em; }
    blockquote {
      border-left: 3px solid #0f1419;
      margin: 1.2em 0;
      padding: 0.1em 1.2em;
      color: #0f1419;
      font-style: italic;
    }
    pre, code {
      font-family: "SF Mono", "Monaco", "Inconsolata", "Fira Code", monospace;
      font-size: 0.88em;
    }
    pre {
      background: #f7f9f9;
      padding: 1.2em;
      border-radius: 4px;
      overflow-x: auto;
    }
    code {
      background: #f7f9f9;
      padding: 0.15em 0.4em;
      border-radius: 3px;
    }
    pre code {
      background: none;
      padding: 0;
    }
    table { border-collapse: collapse; width: 100%; margin-bottom: 1.2em; }
    th, td { border: 1px solid #eff3f4; padding: 0.5em 0.8em; }
    th { background: #f7f9f9; font-weight: 700; }
    hr { border: none; border-top: 1px solid #eff3f4; margin: 2em 0; }
    a { color: inherit; text-decoration: underline; }
    .nb2wb-footer {
      margin-top: 3em;
      padding-top: 1em;
      border-top: 1px solid #eff3f4;
      text-align: center;
      font-size: 0.8em;
      color: #536471;
    }
    .nb2wb-footer a { color: #536471; text-decoration: none; }
    .nb2wb-footer a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div id="toolbar">
    <button id="copy-btn" onclick="copyContent()">&#128203; Copy to clipboard</button>
    <p>Paste into X Articles. If images are missing, hover each one to copy it.</p>
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

        // Unwrap .md-cell and .code-cell divs to avoid empty lines
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


class XArticlesBuilder(PlatformBuilder):
    """
    HTML builder optimized for X (Twitter) Articles.

    Creates an interactive HTML page with copy-to-clipboard buttons for each image,
    since X's editor accepts pasted images but not embedded data URIs.
    """

    @property
    def name(self) -> str:
        return "X Articles"

    def build_page(self, content_html: str) -> str:
        """
        Wrap content in X Articles-optimized HTML page.

        Replaces inline images with interactive containers that have
        "Copy image" buttons using the Clipboard API.
        """
        content_html = self._make_images_copyable(content_html)
        return _HEAD + content_html + _TAIL
