"""Tests for goto language CLI."""

from pathlib import Path

from goto_lang.cli import main


def test_cli_check_mode(tmp_path: Path, capsys) -> None:
    """Check mode validates program without execution."""

    source = tmp_path / "ok.goto"
    source.write_text("start:\nhello\n", encoding="utf-8")

    exit_code = main([str(source), "--check"])

    assert exit_code == 0
    assert "Check successful" in capsys.readouterr().out


def test_cli_inspect_mode(tmp_path: Path, capsys) -> None:
    """Inspect mode renders statement table."""

    source = tmp_path / "ok.goto"
    source.write_text("start:\nhello\n", encoding="utf-8")

    exit_code = main([str(source), "--inspect"])

    assert exit_code == 0
    assert "Statements:" in capsys.readouterr().out
