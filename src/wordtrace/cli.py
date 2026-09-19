"""Word Trace CLI: turn images in input/ into one A4 tracing-worksheet PDF."""

import argparse
import re
import shutil
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from wordtrace.layout import render_page

DEFAULT_HOME = Path.home() / "Documents" / "WordTrace"
CONFIG = Path(__file__).resolve().parents[2] / "wordtrace.toml"


def load_home(config: Path = CONFIG) -> Path:
    """Read the single `home` key from the optional config file."""
    try:
        home = tomllib.loads(config.read_text()).get("home")
    except FileNotFoundError:
        return DEFAULT_HOME
    except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError) as exc:
        print(f"Ignoring {config}: {exc}")
        return DEFAULT_HOME
    return Path(home).expanduser() if home else DEFAULT_HOME


def word_and_letter(stem: str) -> tuple[str, str | None]:
    """Title-case the filename and pick the first alphabetic character."""
    title = re.sub(
        r"[^\W\d_]+'?[^\W\d_]*",
        lambda m: m.group(0)[0].upper() + m.group(0)[1:].lower(),
        stem,
    )
    return title, next((c for c in stem if c.isalpha()), None)


EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def images_in(folder: Path) -> list[Path]:
    """Supported images in the folder, alphabetical, case-insensitive."""
    return sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXTS),
        key=lambda p: p.name.lower(),
    )


def render_pdf(paths: list[Path], pdf_path: Path) -> list[Path]:
    """Render a page per image. Returns the paths that produced a page."""
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    done: list[Path] = []
    for path in paths:
        title, letter = word_and_letter(path.stem)
        if letter is None:
            print(f"Skipped {path.name}: no letter in the filename")
            continue
        try:
            render_page(c, path, title, letter)
        except Exception as exc:
            print(f"Skipped {path.name}: {exc}")
            continue
        done.append(path)
    if done:
        c.save()
    return done


def run(home: Path) -> None:
    """Scan input, write one PDF, move the sources that rendered."""
    print(f"Word Trace home: {home}")
    inbox, outbox, processed = home / "input", home / "output", home / "processed"
    for folder in (inbox, outbox, processed):
        folder.mkdir(parents=True, exist_ok=True)

    paths = images_in(inbox)
    if not paths:
        print("Nothing to do.")
        return

    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    pdf_path = outbox / f"wordtrace-{stamp}.pdf"
    done = render_pdf(paths, pdf_path)
    if not done:
        print("No pages rendered, nothing written.")
        return

    dest = processed / stamp
    dest.mkdir(parents=True, exist_ok=True)
    for path in done:
        shutil.move(str(path), dest / path.name)
    print(f"{len(done)} page(s) -> {pdf_path}")


SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def preview() -> None:
    """Render the committed samples to samples/preview.pdf and open it."""
    pdf_path = SAMPLES / "preview.pdf"
    done = render_pdf(images_in(SAMPLES), pdf_path)
    if not done:
        print(f"No sample images in {SAMPLES}")
        return
    print(f"{len(done)} page(s) -> {pdf_path}")
    subprocess.run(["open", str(pdf_path)], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Make letter-tracing worksheets.")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="render samples/ to samples/preview.pdf and open it",
    )
    if parser.parse_args().preview:
        preview()
    else:
        run(load_home())
