"""Tests for goto language execution."""

from pathlib import Path

import pytest

from goto_lang.interpreter import Interpreter, TraceEvent
from goto_lang.parser import ParseError


def test_program_terminates_when_falling_off_end() -> None:
    """Execution terminates after the last statement."""

    source = "entry:\n"
    result = Interpreter().run(source)
    assert result.terminated is True
    assert result.reason == "completed"
    assert result.steps == 1


def test_compile_rejects_guaranteed_infinite_loop() -> None:
    """Compilation rejects loops that are guaranteed to be infinite."""

    source = "start:\ngoto start\n"
    with pytest.raises(ParseError, match="Infinite loop detected"):
        Interpreter().compile(source)


def test_compile_rejects_unknown_label_reference() -> None:
    """Compilation fails if goto references an undefined label."""

    with pytest.raises(ParseError, match="Unknown label"):
        Interpreter().compile("goto nowhere")


def test_compile_rejects_duplicate_labels() -> None:
    """Compilation fails if a label is defined more than once."""

    with pytest.raises(ParseError, match="Duplicate label"):
        Interpreter().compile("x:\nx:")


def test_compile_rejects_expression_based_infinite_loop() -> None:
    """Compiler rejects expression-based labels when they create a hard loop."""

    source = "\"start\":\ngoto \"s\" + \"tart\"\n"
    with pytest.raises(ParseError, match="Infinite loop detected"):
        Interpreter().compile(source)




def test_unless_true_suppresses_jump_and_program_terminates() -> None:
    """A goto guarded by unless True does not jump."""

    source = "start:\nunless True goto start\n"
    result = Interpreter().run(source)
    assert result.terminated is True
    assert result.reason == "completed"
    assert result.steps == 2


def test_unless_false_allows_jump_and_is_validated_as_infinite() -> None:
    """A goto guarded by unless False still jumps and is compile-time invalid."""

    source = "start:\nunless False goto start\n"
    with pytest.raises(ParseError, match="Infinite loop detected"):
        Interpreter().compile(source)


def test_not_with_unless_true_restores_jump_and_is_validated_as_infinite() -> None:
    """Combining not with unless True restores jump behavior."""

    source = "start:\nnot unless True goto start\n"
    with pytest.raises(ParseError, match="Infinite loop detected"):
        Interpreter().compile(source)


def test_not_modifier_suppresses_goto_jump() -> None:
    """A goto with odd number of `not` modifiers does not jump."""

    source = "start:\nnot goto start\n"
    result = Interpreter().run(source, max_steps=10)
    assert result.terminated is True
    assert result.reason == "completed"
    assert result.steps == 2


def test_not_goto_discards_matching_label_from_stack() -> None:
    """A disabled goto removes its target label from the runtime stack."""

    source = "a:\nb:\nnot goto a\ngoto\n"
    result = Interpreter().run(source)
    assert result.terminated is True
    assert result.reason == "completed"
    assert result.steps == 4


def test_even_not_modifiers_preserve_goto_jump() -> None:
    """A goto with even number of `not` modifiers is validated as looping."""

    source = "start:\nnot not go to start\n"
    with pytest.raises(ParseError, match="Infinite loop detected"):
        Interpreter().compile(source)


def test_external_goto_is_not_treated_as_local_infinite_loop(tmp_path: Path) -> None:
    """Compiler allows unresolved external control flow without false positives."""

    entry = tmp_path / "entry.goto"
    entry.write_text("start:\ngoto next.goto\n", encoding="utf-8")
    (tmp_path / "next.goto").write_text("done:\n", encoding="utf-8")

    result = Interpreter().run_file(entry)
    assert result.terminated is True
    assert result.reason == "completed"


def test_run_file_supports_cross_file_goto_without_label(tmp_path: Path) -> None:
    """Interpreter loads and jumps into another file from a file-only target."""

    entry = tmp_path / "entry.goto"
    next_file = tmp_path / "next.goto"
    entry.write_text("start:\ngoto next.goto\n", encoding="utf-8")
    next_file.write_text("end:\n", encoding="utf-8")

    result = Interpreter().run_file(entry, max_steps=10)
    assert result.terminated is True
    assert result.reason == "completed"
    assert result.steps == 3


def test_run_file_supports_cross_file_goto_with_label(tmp_path: Path) -> None:
    """Interpreter can jump to a specific label inside another file."""

    entry = tmp_path / "entry.goto"
    next_file = tmp_path / "next.goto"
    entry.write_text("start:\ngoto next.goto:target\n", encoding="utf-8")
    next_file.write_text("before:\ntarget:\n", encoding="utf-8")

    result = Interpreter().run_file(entry, max_steps=10)
    assert result.terminated is True
    assert result.reason == "completed"
    assert result.steps == 3


def test_run_file_raises_for_unknown_external_label(tmp_path: Path) -> None:
    """Interpreter raises if a target file does not define the requested label."""

    entry = tmp_path / "entry.goto"
    next_file = tmp_path / "next.goto"
    entry.write_text("start:\ngoto next.goto:missing\n", encoding="utf-8")
    next_file.write_text("present:\n", encoding="utf-8")

    with pytest.raises(ParseError, match="Unknown label 'missing'"):
        Interpreter().run_file(entry)


def test_run_trace_uses_memory_sentinel_for_in_memory_execution() -> None:
    """In-memory execution traces report the sentinel source path."""

    result = Interpreter().run("start:\n", max_steps=10)

    assert result.trace == [TraceEvent(file="<memory>", line=1)]


def test_run_file_trace_captures_file_and_line_across_external_goto(tmp_path: Path) -> None:
    """Trace events include file paths and lines across file transitions."""

    entry = tmp_path / "entry.goto"
    next_file = tmp_path / "next.goto"
    entry.write_text("start:\ngoto next.goto\n", encoding="utf-8")
    next_file.write_text("target:\n", encoding="utf-8")

    result = Interpreter().run_file(entry, max_steps=10)

    assert result.trace == [
        TraceEvent(file=str(entry.resolve()), line=1),
        TraceEvent(file=str(entry.resolve()), line=2),
        TraceEvent(file=str(next_file.resolve()), line=1),
    ]


def test_targetless_goto_pops_label_stack_and_jumps() -> None:
    """A targetless goto pops the latest label and jumps to the new top label."""

    source = "a:\nb:\ngoto\n"
    with pytest.raises(ParseError, match="Infinite loop detected"):
        Interpreter().compile(source)


def test_targetless_goto_errors_without_encountered_labels() -> None:
    """A targetless goto cannot run before any labels have been visited."""

    with pytest.raises(ParseError, match="Cannot execute targetless goto"):
        Interpreter().compile("goto\n")


def test_targetless_goto_can_fall_through_after_popping_last_label() -> None:
    """A targetless goto can terminate after removing the final stack entry."""

    source = "a:\ngoto\n"
    result = Interpreter().run(source)
    assert result.terminated is True
    assert result.reason == "completed"
    assert result.steps == 2


def test_compile_supports_user_function_in_label_and_unless_expression() -> None:
    """Compiler accepts user() inside label and unless expressions when provided."""

    prompts: list[str] = []

    def fake_user(prompt: str) -> object:
        prompts.append(prompt)
        return "loop" if len(prompts) == 1 else True

    program = Interpreter().compile(
        'user("label> "):\nunless user("jump? ") goto loop\n',
        user_function=fake_user,
    )

    assert program.labels == {"loop": 0}
    assert program.statements[1].should_jump is False
    assert prompts == ["label> ", "jump? "]
