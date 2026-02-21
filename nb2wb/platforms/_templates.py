"""
Shared HTML/CSS/JS templates for platform preview pages.
"""
from __future__ import annotations

from string import Template
from typing import Mapping

_BASE_THEME: dict[str, str] = {
    "body-font-family": 'Georgia, "Times New Roman", serif',
    "body-font-size": "18px",
    "body-line-height": "1.7",
    "body-color": "#222",
    "body-max-width": "960px",
    "body-padding": "24px 16px 60px",
    "body-background": "#f0f0f0",
    "toolbar-background": "#1e1e2e",
    "toolbar-color": "#cdd6f4",
    "toolbar-radius": "8px",
    "toolbar-shadow": "0 2px 8px rgba(0,0,0,0.25)",
    "toolbar-button-background": "#89b4fa",
    "toolbar-button-color": "#1e1e2e",
    "toolbar-button-hover-background": "#74c7ec",
    "toolbar-button-radius": "6px",
    "content-background": "#fff",
    "content-padding": "48px 56px",
    "content-radius": "8px",
    "content-shadow": "0 2px 12px rgba(0,0,0,0.08)",
    "md-cell-margin": "1.2em",
    "code-cell-margin": "1.4em 0",
    "heading-font-family": '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
    "heading-font-weight": "700",
    "heading-color": "currentColor",
    "heading-margin": "1.4em 0 0.5em",
    "h1-size": "2em",
    "h2-size": "1.5em",
    "h3-size": "1.17em",
    "h3-letter-spacing": "normal",
    "blockquote-border": "#ddd",
    "blockquote-color": "#666",
    "mono-font-family": '"DejaVu Sans Mono", "Fira Code", Consolas, monospace',
    "mono-font-size": "0.85em",
    "pre-background": "#f4f4f4",
    "pre-padding": "1em",
    "inline-code-background": "transparent",
    "inline-code-padding": "0",
    "inline-code-radius": "0",
    "table-border": "#ddd",
    "table-header-background": "#f4f4f4",
    "hr-border": "#ddd",
    "link-color": "inherit",
    "footer-border": "#eee",
    "footer-color": "#aaa",
    "copy-image-button-background": "rgba(26, 137, 23, 0.9)",
    "copy-image-button-hover-background": "rgba(13, 95, 11, 0.95)",
    "copy-image-button-copied-background": "#0d5f0b",
    "code-image-radius": "5px",
}

COPYABLE_SCRIPT = """\
    async function copyContent() {
      var btn = document.getElementById("copy-btn");
      try {
        var content = document.getElementById("content").cloneNode(true);

        // Unwrap .md-cell and .code-cell divs to avoid empty lines in editors.
        content.querySelectorAll(".md-cell, .code-cell").forEach(function(div) {
          var parent = div.parentNode;
          while (div.firstChild) {
            parent.insertBefore(div.firstChild, div);
          }
          parent.removeChild(div);
        });

        // Unwrap image containers but keep the <img> tags.
        content.querySelectorAll(".image-container").forEach(function(container) {
          var img = container.querySelector("img");
          if (img) {
            container.replaceWith(img);
          }
        });

        // Remove footer from copied content.
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

    // Copy a single image to clipboard.
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

    // Wire up copy-image buttons.
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
"""

SIMPLE_COPY_SCRIPT = """\
    async function copyContent() {
      const el  = document.getElementById("content");
      const btn = document.getElementById("copy-btn");
      try {
        // Modern API: copies rich HTML to clipboard.
        const blob = new Blob([el.innerHTML], { type: "text/html" });
        const item = new ClipboardItem({ "text/html": blob });
        await navigator.clipboard.write([item]);
      } catch (_) {
        // Fallback: select the node and let the browser copy.
        const range = document.createRange();
        range.selectNode(el);
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        document.execCommand("copy");
        window.getSelection().removeAllRanges();
      }
      btn.textContent = "\\u2713 Copied!";
      setTimeout(() => { btn.textContent = "\\u{1F4CB} Copy to clipboard"; }, 2500);
    }
"""

_PAGE_TEMPLATE = Template(
    """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>$title</title>
  <style>
    * { box-sizing: border-box; }
    :root {
$theme_vars
    }
    body {
      font-family: var(--body-font-family);
      font-size: var(--body-font-size);
      line-height: var(--body-line-height);
      color: var(--body-color);
      max-width: var(--body-max-width);
      margin: 0 auto;
      padding: var(--body-padding);
      background: var(--body-background);
    }
    #toolbar {
      position: sticky;
      top: 0;
      z-index: 100;
      background: var(--toolbar-background);
      color: var(--toolbar-color);
      padding: 10px 20px;
      border-radius: var(--toolbar-radius);
      margin-bottom: 28px;
      display: flex;
      align-items: center;
      gap: 16px;
      box-shadow: var(--toolbar-shadow);
    }
    #toolbar button {
      background: var(--toolbar-button-background);
      color: var(--toolbar-button-color);
      border: none;
      padding: 8px 18px;
      font-size: 14px;
      font-weight: 600;
      border-radius: var(--toolbar-button-radius);
      cursor: pointer;
      transition: background 0.15s;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    #toolbar button:hover { background: var(--toolbar-button-hover-background); }
    #toolbar p { margin: 0; font-size: 13px; opacity: 0.9; }
    #content {
      background: var(--content-background);
      padding: var(--content-padding);
      border-radius: var(--content-radius);
      box-shadow: var(--content-shadow);
    }
    .md-cell { margin-bottom: var(--md-cell-margin); }
    .code-cell { margin: var(--code-cell-margin); }
    img {
      max-width: 100%;
      height: auto;
      display: block;
    }
    .code-cell img { border-radius: var(--code-image-radius); }
    .image-container {
      position: relative;
      margin: 0.5em 0;
    }
    .image-container img {
      max-width: 100%;
      height: auto;
      display: block;
      border-radius: var(--code-image-radius);
    }
    .copy-image-btn {
      position: absolute;
      top: 8px;
      right: 8px;
      background: var(--copy-image-button-background);
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
    .copy-image-btn:hover { background: var(--copy-image-button-hover-background); }
    .copy-image-btn.copied {
      opacity: 1;
      background: var(--copy-image-button-copied-background);
    }
    h1, h2, h3, h4, h5, h6 {
      font-family: var(--heading-font-family);
      font-weight: var(--heading-font-weight);
      margin: var(--heading-margin);
      line-height: 1.3;
      color: var(--heading-color);
    }
    h1 { font-size: var(--h1-size); }
    h2 { font-size: var(--h2-size); }
    h3 { font-size: var(--h3-size); letter-spacing: var(--h3-letter-spacing); }
    p { margin: 0 0 1em; }
    ul, ol { margin: 0 0 1em; padding-left: 1.8em; }
    li { margin-bottom: 0.3em; }
    blockquote {
      border-left: 3px solid var(--blockquote-border);
      margin: 1.2em 0;
      padding: 0.1em 1.2em;
      color: var(--blockquote-color);
      font-style: italic;
    }
    pre, code {
      font-family: var(--mono-font-family);
      font-size: var(--mono-font-size);
    }
    pre {
      background: var(--pre-background);
      padding: var(--pre-padding);
      border-radius: 4px;
      overflow-x: auto;
    }
    code {
      background: var(--inline-code-background);
      padding: var(--inline-code-padding);
      border-radius: var(--inline-code-radius);
    }
    pre code {
      background: none;
      padding: 0;
      border-radius: 0;
    }
    table { border-collapse: collapse; width: 100%; margin-bottom: 1.2em; }
    th, td { border: 1px solid var(--table-border); padding: 0.5em 0.8em; }
    th { background: var(--table-header-background); font-weight: 600; }
    hr { border: none; border-top: 1px solid var(--hr-border); margin: 2em 0; }
    a { color: var(--link-color); text-decoration: underline; }
    .nb2wb-footer {
      margin-top: 3em;
      padding-top: 1em;
      border-top: 1px solid var(--footer-border);
      text-align: center;
      font-size: 0.8em;
      color: var(--footer-color);
    }
    .nb2wb-footer a {
      color: var(--footer-color);
      text-decoration: none;
    }
    .nb2wb-footer a:hover { text-decoration: underline; }
$extra_css
  </style>
</head>
<body>
  <div id="toolbar">
    <button id="copy-btn" onclick="copyContent()">&#128203; Copy to clipboard</button>
    <p>$toolbar_message</p>
  </div>
  <div id="content">
$content_html
  <div class="nb2wb-footer">
    Made with <a href="https://github.com/the-palindrome/nb2wb">nb2wb</a>
  </div>
  </div><!-- #content -->
  <script>
$script
  </script>
</body>
</html>
"""
)


def build_page(
    content_html: str,
    *,
    title: str,
    toolbar_message: str,
    script: str,
    theme_overrides: Mapping[str, str] | None = None,
    extra_css: str = "",
) -> str:
    """Build a complete HTML preview page."""
    theme = dict(_BASE_THEME)
    if theme_overrides:
        theme.update(theme_overrides)
    theme_vars = "\n".join(
        f"      --{name}: {value};" for name, value in theme.items()
    )
    return _PAGE_TEMPLATE.substitute(
        title=title,
        theme_vars=theme_vars,
        toolbar_message=toolbar_message,
        content_html=content_html,
        script=script,
        extra_css=extra_css,
    )
