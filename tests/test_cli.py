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
