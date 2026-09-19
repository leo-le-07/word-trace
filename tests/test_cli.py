from pathlib import Path

import pytest

from wordtrace.cli import DEFAULT_HOME, load_home, word_and_letter


def test_missing_config_uses_default(tmp_path):
    assert load_home(tmp_path / "nope.toml") == DEFAULT_HOME


def test_config_home_is_used(tmp_path):
    cfg = tmp_path / "wordtrace.toml"
    cfg.write_text('home = "/tmp/wt"\n')
    assert load_home(cfg) == Path("/tmp/wt")


def test_config_home_expands_tilde(tmp_path):
    cfg = tmp_path / "wordtrace.toml"
    cfg.write_text('home = "~/WT"\n')
    assert load_home(cfg) == Path.home() / "WT"


def test_config_without_home_key_uses_default(tmp_path):
    cfg = tmp_path / "wordtrace.toml"
    cfg.write_text('other = 1\n')
    assert load_home(cfg) == DEFAULT_HOME


def test_malformed_config_warns_and_uses_default(tmp_path, capsys):
    cfg = tmp_path / "wordtrace.toml"
    cfg.write_text("home = [unclosed\n")
    assert load_home(cfg) == DEFAULT_HOME
    assert "wordtrace.toml" in capsys.readouterr().out


@pytest.mark.parametrize(
    "stem,title,letter",
    [
        ("dump truck", "Dump Truck", "d"),
        ("CAT", "Cat", "C"),
        ("dad's car", "Dad's Car", "d"),
        ("T-Rex", "T-Rex", "T"),
        ("3 bears", "3 Bears", "b"),
    ],
)
def test_word_and_letter(stem, title, letter):
    assert word_and_letter(stem) == (title, letter)


def test_word_without_letters_returns_none():
    assert word_and_letter("123") == ("123", None)


from PIL import Image

from wordtrace.cli import images_in, render_pdf, run


def make_image(path, size=(200, 200)):
    img = Image.new("RGB", size, "white")
    img.paste(Image.new("RGB", (size[0] // 2, size[1] // 2), "black"), (10, 10))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def test_images_in_is_alphabetical_and_filters(tmp_path):
    for name in ["cat.png", "apple.jpg", "Bee.JPG", "notes.txt", "x.gif"]:
        (tmp_path / name).write_bytes(b"")
    assert [p.name for p in images_in(tmp_path)] == ["apple.jpg", "Bee.JPG", "cat.png"]


def test_render_pdf_skips_bad_files_and_renders_rest(tmp_path, capsys):
    good = make_image(tmp_path / "cat.png")
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"not an image")
    nameless = make_image(tmp_path / "123.png")

    pdf = tmp_path / "out.pdf"
    done = render_pdf([good, bad, nameless], pdf)

    assert done == [good]
    assert pdf.exists()
    out = capsys.readouterr().out
    assert "broken.png" in out and "123.png" in out


def test_render_pdf_writes_nothing_when_all_fail(tmp_path):
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"not an image")
    pdf = tmp_path / "out.pdf"
    assert render_pdf([bad], pdf) == []
    assert not pdf.exists()


def test_run_creates_tree_and_reports_nothing_to_do(tmp_path, capsys):
    run(tmp_path)
    for sub in ("input", "output", "processed"):
        assert (tmp_path / sub).is_dir()
    out = capsys.readouterr().out
    assert str(tmp_path) in out
    assert "Nothing to do" in out
    assert not list((tmp_path / "output").iterdir())


def test_run_renders_one_pdf_and_moves_sources(tmp_path):
    for name in ("cat.png", "apple.jpg", "dog.png"):
        make_image(tmp_path / "input" / name)
    run(tmp_path)

    pdfs = list((tmp_path / "output").glob("wordtrace-*.pdf"))
    assert len(pdfs) == 1
    assert not list((tmp_path / "input").iterdir())
    stamp_dirs = list((tmp_path / "processed").iterdir())
    assert len(stamp_dirs) == 1
    assert sorted(p.name for p in stamp_dirs[0].iterdir()) == ["apple.jpg", "cat.png", "dog.png"]
    assert stamp_dirs[0].name in pdfs[0].name


def test_run_leaves_failed_image_in_input(tmp_path):
    make_image(tmp_path / "input" / "cat.png")
    (tmp_path / "input" / "broken.png").write_bytes(b"not an image")
    run(tmp_path)

    assert [p.name for p in (tmp_path / "input").iterdir()] == ["broken.png"]
    assert len(list((tmp_path / "output").glob("*.pdf"))) == 1
