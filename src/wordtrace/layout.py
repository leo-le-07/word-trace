"""Page geometry and painting. Every constant here is meant to be tuned
against a printed page using `uv run wordtrace --preview`."""

from pathlib import Path

from PIL import Image

WHITE_TOL = 235  # pixels brighter than this count as background


def prepare_image(path: Path) -> Image.Image:
    """Greyscale the image and crop away its near-white surround."""
    img = Image.open(path)
    img.load()
    img = img.convert("L")
    box = img.point(lambda p: 255 if p < WHITE_TOL else 0).getbbox()
    return img.crop(box) if box else img
