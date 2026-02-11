"""Interpreter for the goto-only language."""

from __future__ import annotations

from dataclasses import dataclass

from .parser import ParseError, ParsedLine, parse_program


@dataclass(frozen=True)
class Statement:
    """Executable representation of a source line."""

    kind: str
    argument: str | None
    source_line: int
    should_jump: bool = True


@dataclass(frozen=True)
class Program:
    """Compiled goto language program."""

    statements: list[Statement]
    labels: dict[str, int]


@dataclass(frozen=True)
class ExecutionResult:
    """Result of a program execution."""

    terminated: bool
    steps: int
    instruction_pointer: int
    reason: str
    trace: list[int]


class Interpreter:
    """Compiler and runtime for the goto-only language."""

    def compile(self, source: str) -> Program:
        """Compile source code into a :class:`Program`.

        Args:
            source: Source code to compile.

        Returns:
            Program: Compiled instructions and label table.

        Raises:
            ParseError: If syntax or label references are invalid.
        """

        parsed = parse_program(source)
        statements: list[Statement] = []
        labels: dict[str, int] = {}

        for line in parsed:
            self._append_statement(line, statements, labels)

        self._validate_goto_targets(statements, labels)
        return Program(statements=statements, labels=labels)

    def run(self, source: str, max_steps: int = 10_000) -> ExecutionResult:
        """Execute source code with a step limit.

        Args:
            source: Program source code.
            max_steps: Maximum executed instruction count.

        Returns:
            ExecutionResult with status and execution trace.

        Raises:
            ParseError: If compilation fails.
        """

        program = self.compile(source)
        return self.run_program(program, max_steps=max_steps)

    def run_program(self, program: Program, max_steps: int = 10_000) -> ExecutionResult:
        """Execute a precompiled :class:`Program`."""

        ip = 0
        steps = 0
        trace: list[int] = []

        while ip < len(program.statements):
            if steps >= max_steps:
                return ExecutionResult(
                    terminated=False,
                    steps=steps,
                    instruction_pointer=ip,
                    reason=f"step limit reached ({max_steps})",
                    trace=trace,
                )

            statement = program.statements[ip]
            trace.append(statement.source_line)
            steps += 1

            if statement.kind == "label":
                ip += 1
            elif statement.kind == "goto":
                if statement.should_jump:
                    assert statement.argument is not None
                    ip = program.labels[statement.argument]
                else:
                    ip += 1
            else:
                raise RuntimeError(f"Unknown statement kind '{statement.kind}'.")

        return ExecutionResult(
            terminated=True,
            steps=steps,
            instruction_pointer=ip,
            reason="completed",
            trace=trace,
        )

    @staticmethod
    def _append_statement(
        line: ParsedLine,
        statements: list[Statement],
        labels: dict[str, int],
    ) -> None:
        """Append one parsed line into compiled statements."""

        if line.label is not None:
            if line.label in labels:
                raise ParseError(
                    f"Duplicate label '{line.label}' found on line {line.index}."
                )
            labels[line.label] = len(statements)
            statements.append(
                Statement(
                    kind="label",
                    argument=line.label,
                    source_line=line.index,
                )
            )
            return

        if line.goto_target is not None:
            statements.append(
                Statement(
                    kind="goto",
                    argument=line.goto_target,
                    should_jump=line.should_jump is not False,
                    source_line=line.index,
                )
            )
            return

        raise ParseError(f"Line {line.index} is neither label nor goto.")

    @staticmethod
    def _validate_goto_targets(
        statements: list[Statement], labels: dict[str, int]
    ) -> None:
        """Ensure each goto instruction references a known label."""

        for statement in statements:
            if statement.kind == "goto" and statement.argument not in labels:
                raise ParseError(
                    f"Unknown label '{statement.argument}' referenced "
                    f"on line {statement.source_line}."
                )
