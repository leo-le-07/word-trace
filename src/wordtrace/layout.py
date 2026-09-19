"""Page geometry and painting. Every constant here is meant to be tuned
against a printed page using `uv run wordtrace --preview`."""

from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

WHITE_TOL = 235  # pixels brighter than this count as background

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

MARGIN = 15 * mm
CONTENT_W = 180 * mm
ILLUS_H = 143 * mm
TITLE_H = 22 * mm
ROW_H = 34 * mm
IMG_PAD = 2 * mm           # keeps the drawing off the title
TITLE_PT = 36
TITLE_FONT = "Helvetica-Bold"
TITLE_BASELINE_UP = 7 * mm  # baseline above the title block bottom
LETTER_PT = 72              # trace glyph size; tune with --preview
LETTERS_PER_ROW = 6
GUIDES_UP = (4.5 * mm, 11.5 * mm, 20.5 * mm, 29.5 * mm)  # desc, base, mid, asc
GUIDE_GREY = 0.75
GUIDE_WIDTH = 0.4
LETTER_GREY = 0.6
TRACE_FONT = "Trace"
FONT_PATH = Path(__file__).resolve().parents[2] / "assets" / "trace-font-for-kids.ttf"

PAGE_W, PAGE_H = A4
ILLUS_BOTTOM = PAGE_H - MARGIN - ILLUS_H
TITLE_BOTTOM = ILLUS_BOTTOM - TITLE_H
ROW_BOTTOMS = [TITLE_BOTTOM - n * ROW_H for n in (1, 2, 3)]


def prepare_image(path: Path) -> Image.Image:
    """Greyscale the image and crop away its near-white surround."""
    img = Image.open(path)
    img.load()
    img = img.convert("L")
    box = img.point(lambda p: 255 if p < WHITE_TOL else 0).getbbox()
    return img.crop(box) if box else img


def _register_font() -> None:
    if TRACE_FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(TRACE_FONT, str(FONT_PATH)))


def _draw_illustration(c, img: Image.Image) -> None:
    max_w, max_h = CONTENT_W - 2 * IMG_PAD, ILLUS_H - 2 * IMG_PAD
    scale = min(max_w / img.width, max_h / img.height)
    w, h = img.width * scale, img.height * scale
    c.drawImage(
        ImageReader(img),
        MARGIN + (CONTENT_W - w) / 2,
        ILLUS_BOTTOM + (ILLUS_H - h) / 2,
        w,
        h,
    )


def _draw_row(c, bottom: float, letter: str) -> None:
    desc, base, mid, asc = (bottom + up for up in GUIDES_UP)
    c.setStrokeColorRGB(GUIDE_GREY, GUIDE_GREY, GUIDE_GREY)
    c.setLineWidth(GUIDE_WIDTH)
    for y in (asc, mid, base, desc):
        c.line(MARGIN, y, MARGIN + CONTENT_W, y)
    c.setFont(TRACE_FONT, LETTER_PT)
    c.setFillColorRGB(LETTER_GREY, LETTER_GREY, LETTER_GREY)
    step = CONTENT_W / LETTERS_PER_ROW
    for i in range(LETTERS_PER_ROW):
        c.drawCentredString(MARGIN + step * (i + 0.5), base, letter)


def render_page(c, image_path: Path, title: str, letter: str) -> None:
    """Paint one worksheet page and finish it."""
    _register_font()
    _draw_illustration(c, prepare_image(image_path))
    c.setFillColorRGB(0, 0, 0)
    c.setFont(TITLE_FONT, TITLE_PT)
    c.drawCentredString(PAGE_W / 2, TITLE_BOTTOM + TITLE_BASELINE_UP, title)
    _draw_row(c, ROW_BOTTOMS[0], letter.upper())
    for bottom in ROW_BOTTOMS[1:]:
        _draw_row(c, bottom, letter.lower())
    c.showPage()
