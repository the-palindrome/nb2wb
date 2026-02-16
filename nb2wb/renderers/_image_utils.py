"""Shared image-processing helpers used by multiple renderers."""
from __future__ import annotations

from PIL import Image, ImageDraw


def round_corners(img: Image.Image, radius: int) -> Image.Image:
    """Apply transparent rounded corners via an alpha-channel mask."""
    rgba = img.convert("RGBA")
    mask = Image.new("L", rgba.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, rgba.width - 1, rgba.height - 1], radius=radius, fill=255)
    rgba.putalpha(mask)
    return rgba
