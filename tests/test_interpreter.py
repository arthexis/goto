"""Tests for goto language execution."""

import pytest

from goto_lang.interpreter import Interpreter
from goto_lang.parser import ParseError


def test_program_terminates_when_falling_off_end() -> None:
    """Execution terminates after the last statement."""

    source = "entry:\n"
    result = Interpreter().run(source)
    assert result.terminated is True
    assert result.reason == "completed"
    assert result.steps == 1


def test_program_stops_on_step_limit_for_loop() -> None:
    """Execution stops when the max step budget is exhausted."""

    source = "start:\ngoto start\n"
    result = Interpreter().run(source, max_steps=5)
    assert result.terminated is False
    assert result.reason == "step limit reached (5)"
    assert result.steps == 5


def test_compile_rejects_unknown_label_reference() -> None:
    """Compilation fails if goto references an undefined label."""

    with pytest.raises(ParseError, match="Unknown label"):
        Interpreter().compile("goto nowhere")


def test_compile_rejects_duplicate_labels() -> None:
    """Compilation fails if a label is defined more than once."""

    with pytest.raises(ParseError, match="Duplicate label"):
        Interpreter().compile("x:\nx:")


def test_program_supports_expression_based_labels() -> None:
    """Interpreter can jump using labels resolved from expressions."""

    source = "\"start\":\ngoto \"s\" + \"tart\"\n"
    result = Interpreter().run(source, max_steps=4)
    assert result.terminated is False
    assert result.reason == "step limit reached (4)"


def test_not_modifier_suppresses_goto_jump() -> None:
    """A goto with odd number of `not` modifiers does not jump."""

    source = "start:\nnot goto start\n"
    result = Interpreter().run(source, max_steps=10)
    assert result.terminated is True
    assert result.reason == "completed"
    assert result.steps == 2


def test_even_not_modifiers_preserve_goto_jump() -> None:
    """A goto with even number of `not` modifiers still jumps."""

    source = "start:\nnot not go to start\n"
    result = Interpreter().run(source, max_steps=5)
    assert result.terminated is False
    assert result.reason == "step limit reached (5)"
