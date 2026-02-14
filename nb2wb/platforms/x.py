"""
X (Twitter) Articles platform HTML builder.
"""
from __future__ import annotations

from .base import PlatformBuilder

# X Articles HTML template
_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>nb2wb — X Article Preview</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 19px;
      line-height: 1.6;
      color: #0f1419;
      max-width: 680px;
      margin: 0 auto;
      padding: 24px 16px 60px;
      background: #f7f9f9;
    }
    #toolbar {
      position: sticky;
      top: 0;
      z-index: 100;
      background: #1d9bf0;
      color: #fff;
      padding: 12px 20px;
      border-radius: 12px;
      margin-bottom: 28px;
      display: flex;
      align-items: center;
      gap: 16px;
      box-shadow: 0 2px 8px rgba(29, 155, 240, 0.3);
    }
    #toolbar button {
      background: #fff;
      color: #1d9bf0;
      border: none;
      padding: 8px 18px;
      font-size: 14px;
      font-weight: 700;
      border-radius: 20px;
      cursor: pointer;
      transition: background 0.2s;
    }
    #toolbar button:hover { background: #e8f5fe; }
    #toolbar p { margin: 0; font-size: 13px; opacity: 0.9; }
    #content {
      background: #fff;
      padding: 40px 48px;
      border-radius: 16px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.12);
    }
    /* --- cell wrappers --- */
    .md-cell { margin-bottom: 1.3em; }
    .code-cell { margin: 1.5em 0; }
    /* --- images --- */
    img {
      max-width: 100%;
      height: auto;
      display: block;
      border-radius: 8px;
    }
    .code-cell img { border-radius: 8px; }
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
      border-left: 4px solid #1d9bf0;
      margin: 1.2em 0;
      padding: 0.3em 1.2em;
      color: #536471;
      font-style: italic;
    }
    pre, code {
      font-family: "SF Mono", "Monaco", "Inconsolata", "Fira Code", monospace;
      font-size: 0.88em;
    }
    pre {
      background: #f7f9f9;
      padding: 1em;
      border-radius: 8px;
      overflow-x: auto;
      border: 1px solid #eff3f4;
    }
    code {
      background: #f7f9f9;
      padding: 0.2em 0.4em;
      border-radius: 4px;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      margin-bottom: 1.2em;
      border: 1px solid #eff3f4;
      border-radius: 8px;
      overflow: hidden;
    }
    th, td {
      border: 1px solid #eff3f4;
      padding: 0.6em 0.8em;
      text-align: left;
    }
    th {
      background: #f7f9f9;
      font-weight: 700;
      color: #0f1419;
    }
    hr {
      border: none;
      border-top: 1px solid #eff3f4;
      margin: 2em 0;
    }
    .nb2wb-footer {
      margin-top: 3em;
      padding-top: 1.2em;
      border-top: 1px solid #eff3f4;
      text-align: center;
      font-size: 0.8em;
      color: #536471;
    }
    .nb2wb-footer a {
      color: #1d9bf0;
      text-decoration: none;
      font-weight: 500;
    }
    .nb2wb-footer a:hover {
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <div id="toolbar">
    <button id="copy-btn" onclick="copyContent()">📋 Copy content</button>
    <p>Then paste into your X Article draft.</p>
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
      const el  = document.getElementById("content");
      const btn = document.getElementById("copy-btn");
      try {
        // Modern API: copies rich HTML to clipboard
        const blob = new Blob([el.innerHTML], { type: "text/html" });
        const item = new ClipboardItem({ "text/html": blob });
        await navigator.clipboard.write([item]);
      } catch (_) {
        // Fallback: select the node and let the browser copy
        const range = document.createRange();
        range.selectNode(el);
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        document.execCommand("copy");
        window.getSelection().removeAllRanges();
      }
      btn.textContent = "✓ Copied!";
      setTimeout(() => { btn.textContent = "📋 Copy content"; }, 2500);
    }
  </script>
</body>
</html>
"""


class XArticlesBuilder(PlatformBuilder):
    """HTML builder optimized for X (Twitter) Articles."""

    @property
    def name(self) -> str:
        return "X Articles"

    def build_page(self, content_html: str) -> str:
        """Wrap content in X Articles-optimized HTML page."""
        return _HEAD + content_html + _TAIL
