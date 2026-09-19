"""Word Trace CLI: turn images in input/ into one A4 tracing-worksheet PDF."""

import re
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


def word_and_letter(stem: str) -> tuple[str, str | None]:
    """Title-case the filename and pick the first alphabetic character."""
    title = re.sub(
        r"[^\W\d_]+'?[^\W\d_]*",
        lambda m: m.group(0)[0].upper() + m.group(0)[1:].lower(),
        stem,
    )
    return title, next((c for c in stem if c.isalpha()), None)
