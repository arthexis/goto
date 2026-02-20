"""Tests for CLI behavior and exit codes."""

from __future__ import annotations

from pathlib import Path

import pytest

from goto_lang.cli import main


def _write_source(path: Path, source: str) -> None:
    """Write source text to a test file."""

    path.write_text(source, encoding="utf-8")


def test_check_succeeds_for_valid_source(tmp_path: Path, capsys) -> None:
    """`--check` exits successfully when source compiles."""

    source_path = tmp_path / "ok.goto"
    _write_source(source_path, "start:\n")

    code = main([str(source_path), "--check"])
    captured = capsys.readouterr()

    assert code == 0
    assert captured.out.strip() == "Check successful."
    assert captured.err == ""


def test_check_returns_parse_error_for_invalid_source(tmp_path: Path, capsys) -> None:
    """`--check` returns parse/compile errors with code 2 and stderr output."""

    source_path = tmp_path / "bad.goto"
    _write_source(source_path, "goto missing\n")

    code = main([str(source_path), "--check"])
    captured = capsys.readouterr()

    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("Parse error: ")


def test_normal_run_exit_codes_remain_unchanged(tmp_path: Path, capsys) -> None:
    """Normal execution still returns 0 for termination and 1 for step-limit stop."""

    terminate_path = tmp_path / "terminate.goto"
    loop_entry_path = tmp_path / "entry.goto"
    loop_next_path = tmp_path / "next.goto"
    _write_source(terminate_path, "done:\n")
    _write_source(loop_entry_path, "start:\ngoto next.goto\n")
    _write_source(loop_next_path, "again:\ngoto entry.goto\n")

    terminate_code = main([str(terminate_path)])
    terminate_output = capsys.readouterr()

    loop_code = main([str(loop_entry_path), "--max-steps", "1"])
    loop_output = capsys.readouterr()

    assert terminate_code == 0
    assert "Program terminated" in terminate_output.out
    assert terminate_output.err == ""

    assert loop_code == 1
    assert "Program stopped" in loop_output.out
    assert loop_output.err == ""


def test_trace_renders_file_and_line_locations(tmp_path: Path, capsys) -> None:
    """`--trace` output prints source locations as file:line entries."""

    source_path = tmp_path / "trace.goto"
    _write_source(source_path, "start:\n")

    code = main([str(source_path), "--trace"])
    captured = capsys.readouterr()

    assert code == 0
    assert f"Trace: [{source_path.resolve()}:1]" in captured.out
    assert captured.err == ""


def test_inspect_prints_compiled_labels_and_statements(tmp_path: Path, capsys) -> None:
    """`--inspect` prints compiled labels and statement metadata."""

    source_path = tmp_path / "inspect.goto"
    _write_source(source_path, '"s" + "tart":\nnot goto "s" + "tart"\n')

    code = main([str(source_path), "--inspect"])
    captured = capsys.readouterr()

    assert code == 0
    assert "Labels: start->0" in captured.out
    assert "[0] label 'start' line=1" in captured.out
    assert "[1] goto 'start' line=2 no-jump" in captured.out
    assert captured.err == ""


def test_check_and_inspect_are_mutually_exclusive(tmp_path: Path) -> None:
    """`--check` and `--inspect` cannot be provided together."""

    source_path = tmp_path / "mode.goto"
    _write_source(source_path, "start:\n")

    with pytest.raises(SystemExit, match="2"):
        main([str(source_path), "--check", "--inspect"])
