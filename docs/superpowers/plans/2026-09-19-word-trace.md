# Word Trace v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `uv run wordtrace` turns images dropped in `~/Documents/WordTrace/input/` into one print-ready A4 tracing-worksheet PDF.

**Architecture:** Two modules. `layout.py` holds every millimetre constant, the Pillow image prep, and the ReportLab page painter. `cli.py` holds config, filesystem lifecycle, and the run loop. State is the filesystem: unprocessed images sit in `input/`, processed ones in `processed/<timestamp>/`. No manifest, no database, no abstraction layer.

**Tech Stack:** Python ≥3.14 (needs `tomllib`), uv, Pillow, ReportLab, argparse, pytest.

**Spec:** `Word Trace v1 Spec.md` (repo root)

## Global Constraints

- Invocation is `uv run wordtrace`. Exactly one flag: `--preview`. No environment variables.
- The only configuration is `~/.wordtrace.toml` with a single key `home`. Missing file or missing key → default `~/Documents/WordTrace`.
- Every run prints the home path it is working from.
- Supported extensions: `.jpg`, `.jpeg`, `.png`, `.webp`. Anything else in the folder is ignored silently.
- Images are processed in alphabetical order by filename; all pages go into one timestamped PDF.
- PDF name: `output/wordtrace-YYYY-MM-DD-HHMM.pdf`. Processed folder: `processed/YYYY-MM-DD-HHMM/<original filename>`. Same timestamp for both, one timestamp per run.
- Images move to `processed/` **only after** the PDF is written successfully. A file that fails to render is named on the terminal and left in `input/`.
- Page is A4 portrait, 15 mm margin all round, nothing in the outer 15 mm.
- Every layout number is a module-level constant meant to be tuned against a printed page via `--preview`. Do not inline magic numbers into drawing code.
- No image thresholding, thickening, contrast boosting, denoising, resolution checks, or line-art detection.
- Tracing font is the committed TTF at `assets/trace-font-for-kids.ttf` (note: the spec says `assets/trace-font.ttf`; the file actually in the repo is `trace-font-for-kids.ttf` — use the real name).
- Commit after every task.

## Review Focus

Failure modes the spec implies but never states, each pinned by a test in the task that owns the code:

1. **Filename with no alphabetic character** (`123.png`, `!!.jpg`) — `next()` over letters raises `StopIteration` and kills the whole run. Expected: name the file, skip it, render the rest. (Task 2 + Task 5)
2. **Blank or all-white image** — `getbbox()` returns `None` and `crop(None)` raises. Expected: draw the image as-is, no crash. (Task 3)
3. **Uppercase or mixed-case extension** (`Truck.JPG`) — a plain `suffix in EXTS` test silently ignores an image the user clearly meant to process. Expected: case-insensitive match. (Task 5)
4. **Malformed or unreadable `~/.wordtrace.toml`** — `tomllib` raises and the tool never starts. Expected: print why it is ignored, fall back to the default home. (Task 1)
5. **Apostrophes and hyphens in filenames** (`dad's car.png`, `T-Rex.png`) — `str.title()` produces `Dad'S Car`. Expected: `Dad's Car`, `T-Rex`. (Task 2)

---

## File Structure

| File | Responsibility |
| --- | --- |
| `pyproject.toml` | uv project, deps, `wordtrace` console script |
| `src/wordtrace/__init__.py` | empty package marker |
| `src/wordtrace/layout.py` | layout constants, image prep, page painting |
| `src/wordtrace/cli.py` | config, folders, run loop, preview, `main()` |
| `tests/test_layout.py` | image prep + geometry + render smoke test |
| `tests/test_cli.py` | config, scanning, run lifecycle, preview |
| `samples/` | committed sample images for `--preview` |
| `assets/trace-font-for-kids.ttf` | already committed |
| `README.md` | five lines: what it is, how to run |

---

### Task 1: Project scaffold and home-path config

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/wordtrace/__init__.py`, `src/wordtrace/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `DEFAULT_HOME: Path`, `CONFIG: Path`, `load_home(config: Path = CONFIG) -> Path`.

- [ ] **Step 1: Create the uv project files**

`pyproject.toml`:

```toml
[project]
name = "wordtrace"
version = "0.1.0"
description = "Letter-tracing worksheet generator"
requires-python = ">=3.14"
dependencies = ["pillow>=10", "reportlab>=4"]

[project.scripts]
wordtrace = "wordtrace.cli:main"

[dependency-groups]
dev = ["pytest>=8"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/wordtrace"]
```

`.gitignore`:

```
.venv/
__pycache__/
*.egg-info/
samples/preview.pdf
```

`src/wordtrace/__init__.py`: empty file.

- [ ] **Step 2: Write the failing test**

`tests/test_cli.py`:

```python
from pathlib import Path

from wordtrace.cli import DEFAULT_HOME, load_home


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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with `ImportError: cannot import name 'DEFAULT_HOME'`

- [ ] **Step 4: Write minimal implementation**

`src/wordtrace/cli.py`:

```python
"""Word Trace CLI: turn images in input/ into one A4 tracing-worksheet PDF."""

import tomllib
from pathlib import Path

DEFAULT_HOME = Path.home() / "Documents" / "WordTrace"
CONFIG = Path.home() / ".wordtrace.toml"


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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .gitignore src tests
git commit -m "feat: uv project scaffold and home-path config"
```

---

### Task 2: Filename to title and traced letter

**Files:**
- Modify: `src/wordtrace/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `word_and_letter(stem: str) -> tuple[str, str | None]` — returns the display title and the first alphabetic character, or `(stem, None)` when the name contains no letter.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`:

```python
import pytest

from wordtrace.cli import word_and_letter


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with `ImportError: cannot import name 'word_and_letter'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/wordtrace/cli.py` (and `import re` at the top):

```python
def word_and_letter(stem: str) -> tuple[str, str | None]:
    """Title-case the filename and pick the first alphabetic character."""
    title = re.sub(
        r"[^\W\d_]+'?[^\W\d_]*",
        lambda m: m.group(0)[0].upper() + m.group(0)[1:].lower(),
        stem,
    )
    return title, next((c for c in stem if c.isalpha()), None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add src/wordtrace/cli.py tests/test_cli.py
git commit -m "feat: derive worksheet title and traced letter from filename"
```

---

### Task 3: Image prep — greyscale, find content, crop

**Files:**
- Create: `src/wordtrace/layout.py`, `tests/test_layout.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `WHITE_TOL: int`, `prepare_image(path: Path) -> PIL.Image.Image` — greyscale (`"L"`) image cropped to its non-white content. Raises on unreadable files (caller handles).

- [ ] **Step 1: Write the failing test**

`tests/test_layout.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_layout.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'wordtrace.layout'`

- [ ] **Step 3: Write minimal implementation**

`src/wordtrace/layout.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_layout.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/wordtrace/layout.py tests/test_layout.py
git commit -m "feat: greyscale and crop source images to their content"
```

---

### Task 4: Page geometry and rendering

**Files:**
- Modify: `src/wordtrace/layout.py`
- Test: `tests/test_layout.py`

**Interfaces:**
- Consumes: `prepare_image` (Task 3).
- Produces: `render_page(c: reportlab.pdfgen.canvas.Canvas, image_path: Path, title: str, letter: str) -> None` — paints one A4 page and calls `c.showPage()`. Also the constants `MARGIN`, `CONTENT_W`, `ILLUS_H`, `TITLE_H`, `ROW_H`, `ILLUS_BOTTOM`, `TITLE_BOTTOM`, `ROW_BOTTOMS`, `PAGE_W`, `PAGE_H`.

Geometry, top to bottom, from the spec: illustration 143 mm, title 22 mm, uppercase row 34 mm, two lowercase rows 34 mm each; 15 mm margins; 143+22+34+68 = 267 = 297 − 2×15. Within a 34 mm row, the four guide lines sit at 4.5 / 11.5 / 20.5 / 29.5 mm above the row bottom (descender, baseline, midline, ascender), a 25 mm band with 4.5 mm clear above and below.

- [ ] **Step 1: Write the failing geometry test**

Append to `tests/test_layout.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_layout.py -v`
Expected: FAIL with `AttributeError: module 'wordtrace.layout' has no attribute 'ILLUS_H'`

- [ ] **Step 3: Add the constants**

Add to `src/wordtrace/layout.py` below `WHITE_TOL`:

```python
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
```

- [ ] **Step 4: Run geometry tests to verify they pass**

Run: `uv run pytest tests/test_layout.py -v`
Expected: 8 passed

- [ ] **Step 5: Write the failing render test**

Append to `tests/test_layout.py`:

```python
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
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_layout.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_page'`

- [ ] **Step 7: Write the painter**

Add to `src/wordtrace/layout.py` (imports: `from reportlab.lib.utils import ImageReader`, `from reportlab.pdfbase import pdfmetrics`, `from reportlab.pdfbase.ttfonts import TTFont`):

```python
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
```

- [ ] **Step 8: Run all tests**

Run: `uv run pytest -v`
Expected: all passed (10 in `test_layout.py`)

- [ ] **Step 9: Commit**

```bash
git add src/wordtrace/layout.py tests/test_layout.py
git commit -m "feat: A4 worksheet page geometry and rendering"
```

---

### Task 5: Run loop — scan, render, move

**Files:**
- Modify: `src/wordtrace/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_home`, `word_and_letter` (Tasks 1–2), `render_page` (Task 4).
- Produces:
  - `EXTS: set[str]`
  - `images_in(folder: Path) -> list[Path]` — supported images, alphabetical, case-insensitive.
  - `render_pdf(paths: list[Path], pdf_path: Path) -> list[Path]` — renders what it can, returns the paths that made a page; writes the PDF only if at least one page rendered.
  - `run(home: Path) -> None` — full lifecycle for one real run.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with `ImportError: cannot import name 'images_in'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/wordtrace/cli.py` (imports: `shutil`, `from datetime import datetime`, `from reportlab.lib.pagesizes import A4`, `from reportlab.pdfgen import canvas`, `from wordtrace.layout import render_page`):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/wordtrace/cli.py tests/test_cli.py
git commit -m "feat: scan input, render one PDF, move processed images"
```

---

### Task 6: Preview mode, entry point, samples, README

**Files:**
- Modify: `src/wordtrace/cli.py`
- Create: `samples/` (3 committed images), `README.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `images_in`, `render_pdf`, `run`, `load_home`.
- Produces: `SAMPLES: Path`, `preview() -> None`, `main() -> None` (the `wordtrace` console script).

- [ ] **Step 1: Add sample images**

Put three line-art images in `samples/`, named after their words — e.g. `apple.png`, `dump truck.jpg`, `cat.png`. One portrait, one landscape, one with a thick white border, so the preview exercises the layout. Small files; they get committed.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_cli.py`:

```python
from wordtrace import cli


def test_preview_writes_and_opens_one_pdf(tmp_path, monkeypatch):
    samples = tmp_path / "samples"
    make_image(samples / "cat.png")
    make_image(samples / "dog.png")
    monkeypatch.setattr(cli, "SAMPLES", samples)
    opened = []
    monkeypatch.setattr(cli.subprocess, "run", lambda cmd, **kw: opened.append(cmd))

    cli.preview()
    cli.preview()

    pdfs = list(samples.glob("*.pdf"))
    assert [p.name for p in pdfs] == ["preview.pdf"]
    assert sorted(p.name for p in samples.glob("*.png")) == ["cat.png", "dog.png"]
    assert len(opened) == 2


def test_preview_with_no_samples_says_so(tmp_path, monkeypatch, capsys):
    samples = tmp_path / "samples"
    samples.mkdir()
    monkeypatch.setattr(cli, "SAMPLES", samples)
    monkeypatch.setattr(cli.subprocess, "run", lambda cmd, **kw: None)
    cli.preview()
    assert "No sample images" in capsys.readouterr().out
    assert not list(samples.glob("*.pdf"))


def test_main_preview_flag_does_not_touch_home(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "preview", lambda: calls.append("preview"))
    monkeypatch.setattr(cli, "run", lambda home: calls.append("run"))
    monkeypatch.setattr(sys, "argv", ["wordtrace", "--preview"])
    cli.main()
    assert calls == ["preview"]


def test_main_without_flag_runs(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "preview", lambda: calls.append("preview"))
    monkeypatch.setattr(cli, "run", lambda home: calls.append(("run", home)))
    monkeypatch.setattr(sys, "argv", ["wordtrace"])
    cli.main()
    assert calls == [("run", cli.load_home())]
```

Add `import sys` to the test file's imports.

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with `AttributeError: module 'wordtrace.cli' has no attribute 'SAMPLES'`

- [ ] **Step 4: Write minimal implementation**

Add to `src/wordtrace/cli.py` (imports: `argparse`, `subprocess`):

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all passed

- [ ] **Step 6: Check the real thing, on paper**

```bash
uv run wordtrace --preview
```

Expected: `samples/preview.pdf` opens with one page per sample. Print it at 100% (no "fit to page") and check: A4 portrait, nothing in the outer 15 mm, guide lines light enough to write over, tracing letters the right size for a child's hand. If a number is off, tune the constant in `layout.py` (`LETTER_PT`, `GUIDES_UP`, `TITLE_PT`, `GUIDE_GREY`, `LETTER_GREY`) and re-run. That tuning is expected, not a bug.

- [ ] **Step 7: Write the README**

`README.md`:

```markdown
# Word Trace

Letter-tracing worksheets for A4. Drop images named after their word into
`~/Documents/WordTrace/input/`, then:

    uv run wordtrace

One page per image, one timestamped PDF in `output/`, sources moved to
`processed/`. Tune the layout with `uv run wordtrace --preview`.
Optional `~/.wordtrace.toml`: `home = "/path/to/WordTrace"`.
```

- [ ] **Step 8: Commit**

```bash
git add src/wordtrace/cli.py tests/test_cli.py samples README.md
git commit -m "feat: preview mode, CLI entry point, samples, README"
```

---

## Acceptance check (after Task 6)

Walk the spec's acceptance criteria against a real home folder:

```bash
mkdir -p ~/Documents/WordTrace/input
cp samples/*.png samples/*.jpg ~/Documents/WordTrace/input/
printf 'garbage' > ~/Documents/WordTrace/input/broken.png
uv run wordtrace
```

Expect: home path printed, `broken.png` named and still in `input/`, every
other image gone from `input/` and present under `processed/<stamp>/`, one
`output/wordtrace-<stamp>.pdf` whose stamp matches the processed folder, and
`Dump Truck` with `D`/`d` rows on its page. Run `uv run wordtrace` again:
`Nothing to do.`
