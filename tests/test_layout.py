import pytest
from PIL import Image

from wordtrace.layout import prepare_image


def _write(tmp_path, img, name="x.png"):
    p = tmp_path / name
    img.save(p)
    return p


def test_crops_white_border(tmp_path):
    img = Image.new("RGB", (100, 100), "white")
    img.paste(Image.new("RGB", (20, 10), "black"), (40, 45))
    out = prepare_image(_write(tmp_path, img))
    assert out.size == (20, 10)
    assert out.mode == "L"


def test_crops_offcentre_content(tmp_path):
    img = Image.new("RGB", (100, 100), "white")
    img.paste(Image.new("RGB", (10, 10), "black"), (0, 0))
    assert prepare_image(_write(tmp_path, img)).size == (10, 10)


def test_offwhite_background_is_ignored(tmp_path):
    img = Image.new("L", (50, 50), 248)  # scanner off-white
    img.paste(Image.new("L", (10, 10), 0), (20, 20))
    assert prepare_image(_write(tmp_path, img)).size == (10, 10)


def test_blank_image_is_returned_whole(tmp_path):
    img = Image.new("RGB", (30, 40), "white")
    assert prepare_image(_write(tmp_path, img)).size == (30, 40)


def test_unreadable_file_raises(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    with pytest.raises(Exception):
        prepare_image(bad)


from reportlab.lib.units import mm

from wordtrace import layout


def test_blocks_fill_the_page_exactly():
    assert layout.ILLUS_H + layout.TITLE_H + 3 * layout.ROW_H == pytest.approx(
        layout.PAGE_H - 2 * layout.MARGIN
    )


def test_content_stays_inside_margins():
    assert layout.MARGIN + layout.CONTENT_W == pytest.approx(layout.PAGE_W - layout.MARGIN)
    assert layout.ILLUS_BOTTOM + layout.ILLUS_H == pytest.approx(layout.PAGE_H - layout.MARGIN)
    assert layout.ROW_BOTTOMS[-1] == pytest.approx(layout.MARGIN)


def test_rows_are_evenly_stacked():
    tops = [b + layout.ROW_H for b in layout.ROW_BOTTOMS]
    assert tops[0] == pytest.approx(layout.TITLE_BOTTOM)
    assert tops[1] == pytest.approx(layout.ROW_BOTTOMS[0])
    assert tops[2] == pytest.approx(layout.ROW_BOTTOMS[1])


from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from wordtrace.layout import render_page


def test_render_page_writes_a_one_page_a4_pdf(tmp_path):
    img = Image.new("RGB", (400, 200), "white")
    img.paste(Image.new("RGB", (200, 100), "black"), (100, 50))
    src = _write(tmp_path, img, "dump truck.png")

    pdf = tmp_path / "out.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    render_page(c, src, "Dump Truck", "d")
    c.save()

    assert pdf.read_bytes().startswith(b"%PDF")
    assert c.getPageNumber() == 2  # showPage() advanced past page 1


def test_render_page_accepts_portrait_and_landscape(tmp_path):
    pdf = tmp_path / "two.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    for name, size in (("tall.png", (200, 900)), ("wide.png", (900, 200))):
        img = Image.new("RGB", size, "white")
        img.paste(Image.new("RGB", (size[0] // 2, size[1] // 2), "black"), (10, 10))
        render_page(c, _write(tmp_path, img, name), "X", "x")
    c.save()
    assert c.getPageNumber() == 3
