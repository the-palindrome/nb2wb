"""
Assemble the final HTML page from converted cell fragments.
"""
from __future__ import annotations

# Split into head/tail so we never have to escape CSS/JS braces
_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>nb2wb — Substack Preview</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: Georgia, "Times New Roman", serif;
      font-size: 18px;
      line-height: 1.7;
      color: #222;
      max-width: 960px;
      margin: 0 auto;
      padding: 24px 16px 60px;
      background: #f0f0f0;
    }
    #toolbar {
      position: sticky;
      top: 0;
      z-index: 100;
      background: #1e1e2e;
      color: #cdd6f4;
      padding: 10px 20px;
      border-radius: 8px;
      margin-bottom: 28px;
      display: flex;
      align-items: center;
      gap: 16px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    }
    #toolbar button {
      background: #89b4fa;
      color: #1e1e2e;
      border: none;
      padding: 8px 18px;
      font-size: 14px;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
      transition: background 0.15s;
    }
    #toolbar button:hover { background: #74c7ec; }
    #toolbar p { margin: 0; font-size: 13px; opacity: 0.7; }
    #content {
      background: #fff;
      padding: 48px 56px;
      border-radius: 8px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    }
    /* --- cell wrappers --- */
    .md-cell { margin-bottom: 1.2em; }
    .code-cell { margin: 1.4em 0; }
    /* --- images --- */
    img {
      max-width: 100%;
      height: auto;
      display: block;
    }
    .code-cell img { border-radius: 5px; }
    /* --- markdown typography --- */
    h1, h2, h3, h4, h5, h6 {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      margin: 1.4em 0 0.5em;
      line-height: 1.3;
    }
    p { margin: 0 0 1em; }
    ul, ol { margin: 0 0 1em; padding-left: 1.6em; }
    li { margin-bottom: 0.25em; }
    blockquote {
      border-left: 4px solid #ddd;
      margin: 1em 0;
      padding: 0.2em 1em;
      color: #666;
    }
    pre, code {
      font-family: "DejaVu Sans Mono", "Fira Code", Consolas, monospace;
      font-size: 0.85em;
    }
    pre {
      background: #f4f4f4;
      padding: 1em;
      border-radius: 4px;
      overflow-x: auto;
    }
    table { border-collapse: collapse; width: 100%; margin-bottom: 1em; }
    th, td { border: 1px solid #ddd; padding: 0.4em 0.8em; }
    th { background: #f4f4f4; }
    hr { border: none; border-top: 1px solid #ddd; margin: 2em 0; }
    .nb2wb-footer {
      margin-top: 3em;
      padding-top: 1em;
      border-top: 1px solid #eee;
      text-align: center;
      font-size: 0.8em;
      color: #aaa;
    }
    .nb2wb-footer a { color: #aaa; text-decoration: none; }
    .nb2wb-footer a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div id="toolbar">
    <button id="copy-btn" onclick="copyContent()">&#128203; Copy to clipboard</button>
    <p>Then paste directly into your Substack draft.</p>
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
      btn.textContent = "\\u2713 Copied!";
      setTimeout(() => { btn.textContent = "\\u{1F4CB} Copy to clipboard"; }, 2500);
    }
  </script>
</body>
</html>
"""


def build_page(content_html: str) -> str:
    """Wrap *content_html* in the full standalone HTML page."""
    return _HEAD + content_html + _TAIL
