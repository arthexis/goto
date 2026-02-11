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
