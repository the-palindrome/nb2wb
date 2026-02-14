"""
X (Twitter) Articles platform HTML builder.

X's editor doesn't support base64 data URIs, but accepts images pasted from clipboard.
This builder creates an interactive HTML with "Copy image" buttons for each image.
"""
from __future__ import annotations

import re
from .base import PlatformBuilder

# X Articles HTML template with interactive image copying
_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>nb2wb — X Article Interactive Preview</title>
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
      padding: 16px 20px;
      border-radius: 12px;
      margin-bottom: 28px;
      box-shadow: 0 2px 8px rgba(29, 155, 240, 0.3);
    }
    #toolbar h2 {
      margin: 0 0 8px 0;
      font-size: 18px;
      font-weight: 700;
    }
    #toolbar p {
      margin: 4px 0;
      font-size: 14px;
      opacity: 0.95;
      line-height: 1.4;
    }
    #toolbar ol {
      margin: 8px 0 0 0;
      padding-left: 20px;
      font-size: 13px;
      opacity: 0.9;
    }
    #toolbar li {
      margin: 4px 0;
    }
    #content {
      background: #fff;
      padding: 40px 48px;
      border-radius: 16px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.12);
    }
    /* Image containers with copy buttons */
    .image-container {
      margin: 1.5em 0;
      border: 2px solid #1d9bf0;
      border-radius: 12px;
      padding: 16px;
      background: #f7f9f9;
    }
    .image-container img {
      max-width: 100%;
      height: auto;
      display: block;
      border-radius: 8px;
      margin-bottom: 12px;
      border: 1px solid #eff3f4;
    }
    .copy-image-btn {
      width: 100%;
      background: #1d9bf0;
      color: #fff;
      border: none;
      padding: 12px 20px;
      font-size: 15px;
      font-weight: 700;
      border-radius: 20px;
      cursor: pointer;
      transition: background 0.2s;
      font-family: inherit;
    }
    .copy-image-btn:hover {
      background: #1a8cd8;
    }
    .copy-image-btn:active {
      background: #1570b5;
    }
    .copy-image-btn.copied {
      background: #00ba7c;
    }
    .image-number {
      display: inline-block;
      background: #1d9bf0;
      color: #fff;
      padding: 4px 10px;
      border-radius: 12px;
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 8px;
    }
    /* --- markdown typography --- */
    .md-cell { margin-bottom: 1.3em; }
    .code-cell { margin: 1.5em 0; }
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
    <h2>📋 How to copy to X Articles</h2>
    <ol>
      <li><strong>Click each "Copy image" button below</strong> (they'll turn green)</li>
      <li><strong>Paste into your X Article draft</strong> at the corresponding position</li>
      <li><strong>Copy the text content</strong> (Ctrl+C / Cmd+C the text portions) and paste around the images</li>
    </ol>
    <p style="margin-top: 12px; font-size: 13px; opacity: 0.85;">
      💡 <strong>Tip:</strong> X's editor will automatically upload images when you paste them from clipboard.
    </p>
  </div>
  <div id="content">
"""

_TAIL = """\
  <div class="nb2wb-footer">
    Made with <a href="https://github.com/the-palindrome/nb2wb">nb2wb</a>
  </div>
  </div><!-- #content -->

  <script>
    // Copy image to clipboard when button is clicked
    async function copyImageToClipboard(imgSrc, button) {
      try {
        let blob;
        let mimeType;

        // Check if it's a data URI or external URL
        if (imgSrc.startsWith('data:')) {
          // Handle data URI (base64 encoded)
          const base64Data = imgSrc.split(',')[1];
          mimeType = imgSrc.match(/data:([^;]+);/)[1];
          const byteCharacters = atob(base64Data);
          const byteNumbers = new Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
          }
          const byteArray = new Uint8Array(byteNumbers);
          blob = new Blob([byteArray], { type: mimeType });
        } else {
          // Handle external URL - fetch the image
          button.textContent = '⏳ Fetching image...';
          const response = await fetch(imgSrc);
          blob = await response.blob();
          mimeType = blob.type;
        }

        // Copy to clipboard using Clipboard API
        const item = new ClipboardItem({ [mimeType]: blob });
        await navigator.clipboard.write([item]);

        // Update button state
        const originalText = button.textContent;
        button.textContent = '✓ Copied! Now paste in X editor';
        button.classList.add('copied');

        setTimeout(() => {
          button.textContent = originalText;
          button.classList.remove('copied');
        }, 3000);
      } catch (err) {
        console.error('Failed to copy image:', err);
        button.textContent = '❌ Copy failed (try right-click → Copy image)';
        setTimeout(() => {
          button.textContent = '📋 Copy this image';
        }, 3000);
      }
    }

    // Auto-setup copy buttons on page load
    document.addEventListener('DOMContentLoaded', () => {
      const containers = document.querySelectorAll('.image-container');
      containers.forEach((container, index) => {
        const img = container.querySelector('img');
        const btn = container.querySelector('.copy-image-btn');
        if (img && btn) {
          btn.addEventListener('click', () => {
            copyImageToClipboard(img.src, btn);
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

    def _make_images_copyable(self, html: str) -> str:
        """
        Wrap each <img> tag in a container with a copy-to-clipboard button.

        Handles both data URI images and externally linked images.
        Returns modified HTML with interactive image containers.
        """
        # Pattern to match ALL img tags (data URIs, external URLs, self-closing or not)
        img_pattern = re.compile(
            r'<img\s+[^>]*src="([^"]+)"[^>]*/?>',
            re.IGNORECASE
        )

        image_counter = [0]  # Use list for mutability in nested function

        def wrap_image(match: re.Match) -> str:
            image_counter[0] += 1
            img_src = match.group(1)
            # Extract alt text if present, otherwise use default
            full_tag = match.group(0)
            alt_match = re.search(r'alt="([^"]*)"', full_tag)
            alt_text = alt_match.group(1) if alt_match else f"Image {image_counter[0]}"

            return f'''<div class="image-container">
  <div class="image-number">Image {image_counter[0]}</div>
  <img src="{img_src}" alt="{alt_text}">
  <button class="copy-image-btn" type="button">📋 Copy this image</button>
</div>'''

        modified_html = img_pattern.sub(wrap_image, html)
        return modified_html
