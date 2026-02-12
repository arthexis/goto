"""Tests for goto language parsing."""

import pytest

from goto_lang.parser import ParseError, parse_program


def test_parse_valid_program() -> None:
    """Parser accepts labels and goto statements."""

    parsed = parse_program("start:\ngoto start\n")
    assert len(parsed) == 2
    assert parsed[0].label == "start"
    assert parsed[1].goto_target == "start"


def test_reject_unknown_statement() -> None:
    """Parser rejects statements other than labels and goto."""

    with pytest.raises(ParseError, match="Only labels and goto"):
        parse_program("print hello")


def test_parse_label_expressions() -> None:
    """Parser resolves string concatenation and stringifies label values."""

    parsed = parse_program("\"a\" + \"b\":\n")
    assert parsed[0].label == "ab"


def test_parse_numeric_expressions() -> None:
    """Parser resolves numeric arithmetic expressions."""

    parsed = parse_program("start:\ngoto 10 * 2 + 5\n")
    assert parsed[1].goto_target == "25"


def test_parse_case_insensitive_goto_and_go_to() -> None:
    """Parser accepts goto spellings in any case, including 'go to'."""

    parsed = parse_program("start:\nGo To start\nGOTO start\n")
    assert parsed[1].goto_target == "start"
    assert parsed[2].goto_target == "start"


def test_parse_prefix_modifiers_update_jump_behavior() -> None:
    """Prefix modifiers are accepted and odd `not` disables a jump."""

    parsed = parse_program("start:\nplease do not goto start\ndo NOT not go to start\n")
    assert parsed[1].should_jump is False
    assert parsed[2].should_jump is True


def test_parse_file_targets_with_or_without_label() -> None:
    """Parser accepts `goto file.goto` and `goto file.goto:label` targets."""

    parsed = parse_program("start:\ngoto next.goto\ngoto next.goto:entry\n")
    assert parsed[1].goto_target == "next.goto"
    assert parsed[2].goto_target == "next.goto:entry"


def test_parse_file_and_label_with_space_separator() -> None:
    """Parser normalizes `goto file.goto label` into colon form."""

    parsed = parse_program("start:\ngoto next.goto entry\n")
    assert parsed[1].goto_target == "next.goto:entry"


def test_reject_invalid_expression() -> None:
    """Parser raises when expressions cannot be evaluated."""

    with pytest.raises(ParseError, match="Invalid expression"):
        parse_program("goto unknown +")


def test_reject_dangerous_expression_calls() -> None:
    """Parser rejects expressions that attempt to execute code via calls."""

    with pytest.raises(ParseError, match="Invalid expression"):
        parse_program('goto __import__("os").system("echo hacked")')
