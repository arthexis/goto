"""Tests for the goto-only language parser and runtime."""

from __future__ import annotations

import pytest

from goto_lang.language import ParseError, RuntimeExecutionError, parse_program



def test_parse_and_normalize_program() -> None:
    """Parser should accept labels and gotos and produce normalized output."""

    source = """
# Comment line
entry:
  goto loop
loop:
  goto loop
"""
    program = parse_program(source)
    assert program.normalize() == "entry:\ngoto loop\nloop:\ngoto loop"



def test_detect_duplicate_label() -> None:
    """Duplicate labels should produce a parse error."""

    source = """
start:
goto end
start:
"""
    with pytest.raises(ParseError, match="duplicate label"):
        parse_program(source)



def test_reject_invalid_symbol() -> None:
    """Symbols must follow identifier rules."""

    with pytest.raises(ParseError, match="must start"):
        parse_program("goto 9bad")



def test_runtime_unknown_label() -> None:
    """Runtime should fail when jumping to a missing label."""

    program = parse_program("goto nowhere")
    with pytest.raises(RuntimeExecutionError, match="unknown label"):
        program.run()



def test_runtime_timeout_loop() -> None:
    """Infinite loops should stop at max_steps."""

    source = """
loop:
goto loop
"""
    program = parse_program(source)
    with pytest.raises(TimeoutError, match="max_steps"):
        program.run(max_steps=5)



def test_empty_program_runs() -> None:
    """Empty programs should parse and execute without trace output."""

    program = parse_program("\n# only comments\n")
    assert program.run() == []
