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
    """Parser resolves expressions and stringifies label values."""

    parsed = parse_program("\"a\" + \"b\":\ngoto 10 * 2\n")
    assert parsed[0].label == "ab"
    assert parsed[1].goto_target == "20"


def test_reject_invalid_expression() -> None:
    """Parser raises when expressions cannot be evaluated."""

    with pytest.raises(ParseError, match="Invalid expression"):
        parse_program("goto unknown +")
