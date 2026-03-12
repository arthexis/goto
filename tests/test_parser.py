"""Tests for goto language parsing."""

import pytest

from goto_lang.parser import ParseError, parse_program, resolve_expression


def test_parse_text_line_as_output() -> None:
    """Parser keeps free text lines as output statements."""

    parsed = parse_program("hello world")
    assert parsed[0].output_text == "hello world"
    assert parsed[0].is_goto is False


def test_parse_goto_keeps_output_and_unless_decision_text() -> None:
    """Parser splits prefix into output text and unless decision text."""

    parsed = parse_program("Show this unless decide based on this goto done")
    assert parsed[0].is_goto is True
    assert parsed[0].output_text == "Show this"
    assert parsed[0].decision_text == "decide based on this"
    assert parsed[0].goto_targets == ("done",)


def test_parse_not_and_please_modifiers() -> None:
    """Parser tracks `not` count and `please` usage."""

    parsed = parse_program("please not goto done")
    assert parsed[0].please is True
    assert parsed[0].not_count == 1


def test_parse_goto_targets_keep_runtime_expressions() -> None:
    """Goto target expressions stay raw for runtime sigil resolution."""

    parsed = parse_program("goto [path] + 3, `fallback`")
    assert parsed[0].goto_targets == ("[path] + 3", "`fallback`")


def test_parse_goto_ignores_keyword_in_backticks() -> None:
    """Backtick strings keep embedded goto text as plain output."""

    parsed = parse_program("`do not goto there`")
    assert parsed[0].is_goto is False


def test_resolve_expression_walrus_requires_expression_context() -> None:
    """Top-level walrus is rejected because it is not a standalone statement."""

    with pytest.raises(ParseError):
        resolve_expression("welcome := 'hello'", 1, sigils={})
