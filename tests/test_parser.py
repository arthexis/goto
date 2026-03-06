"""Tests for goto language parsing."""

from goto_lang.parser import parse_program


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
