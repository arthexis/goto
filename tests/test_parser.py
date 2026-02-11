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


def test_reject_bad_label_name() -> None:
    """Parser rejects labels with invalid names."""

    with pytest.raises(ParseError, match="Invalid label"):
        parse_program("123:")
