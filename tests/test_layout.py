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
