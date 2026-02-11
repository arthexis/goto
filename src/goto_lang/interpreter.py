"""Interpreter for the goto-only language."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .parser import FILE_REFERENCE_PATTERN, ParseError, ParsedLine, parse_program


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
        self._validate_not_guaranteed_infinite(statements, labels)
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

    def run_file(self, source_path: Path | str, max_steps: int = 10_000) -> ExecutionResult:
        """Execute a program loaded from disk, supporting cross-file gotos.

        Args:
            source_path: File path to the program entrypoint.
            max_steps: Maximum executed instruction count.

        Returns:
            ExecutionResult with status and execution trace.
        """

        path = Path(source_path).resolve()
        source = path.read_text(encoding="utf-8")
        program = self.compile(source)
        return self._run_with_context(program, max_steps=max_steps, current_path=path)

    def run_program(self, program: Program, max_steps: int = 10_000) -> ExecutionResult:
        """Execute a precompiled :class:`Program`."""

        return self._run_with_context(program, max_steps=max_steps)

    def _run_with_context(
        self,
        program: Program,
        max_steps: int,
        current_path: Path | None = None,
    ) -> ExecutionResult:
        """Execute a program, optionally allowing file-based goto targets."""

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
                    external_target = self._parse_external_target(statement.argument)
                    if external_target is not None:
                        if current_path is None:
                            raise ParseError(
                                "File-based goto requires execution from a file path."
                            )
                        program, ip, current_path = self._load_external_program(
                            current_path,
                            external_target[0],
                            external_target[1],
                        )
                    else:
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
    def _parse_external_target(target: str) -> tuple[str, str | None] | None:
        """Parse `<file>.goto` or `<file>.goto:<label>` goto targets."""

        match = FILE_REFERENCE_PATTERN.match(target)
        if not match:
            return None
        return match.group("file"), match.group("label")

    def _load_external_program(
        self,
        current_path: Path,
        file_target: str,
        label_target: str | None,
    ) -> tuple[Program, int, Path]:
        """Load a target file and compute the target instruction pointer."""

        target_path = (current_path.parent / file_target).resolve()
        source = target_path.read_text(encoding="utf-8")
        target_program = self.compile(source)

        if label_target is None:
            return target_program, 0, target_path

        if label_target not in target_program.labels:
            raise ParseError(
                f"Unknown label '{label_target}' referenced in file '{file_target}'."
            )
        return target_program, target_program.labels[label_target], target_path

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
        """Ensure each goto instruction references a known local label or file target."""

        for statement in statements:
            if statement.kind != "goto":
                continue
            if statement.argument in labels:
                continue
            if Interpreter._parse_external_target(statement.argument or "") is not None:
                continue
            raise ParseError(
                f"Unknown label '{statement.argument}' referenced "
                f"on line {statement.source_line}."
            )

    @staticmethod
    def _validate_not_guaranteed_infinite(
        statements: list[Statement], labels: dict[str, int]
    ) -> None:
        """Reject programs whose local control flow is provably non-terminating.

        The goto language has deterministic control flow for local jumps, so from
        any instruction there is exactly one next instruction pointer. A program
        terminates only when the pointer falls past the final statement.

        This validator follows the local control-flow path from instruction ``0``.
        If it revisits an instruction before leaving the program, termination is
        impossible and compilation fails.
        """

        if not statements:
            return

        seen_instruction_pointers: set[int] = set()
        instruction_pointer = 0

        while instruction_pointer < len(statements):
            if instruction_pointer in seen_instruction_pointers:
                looping_statement = statements[instruction_pointer]
                raise ParseError(
                    "Infinite loop detected at "
                    f"line {looping_statement.source_line}."
                )

            seen_instruction_pointers.add(instruction_pointer)
            statement = statements[instruction_pointer]

            if statement.kind == "label":
                instruction_pointer += 1
                continue

            if statement.kind != "goto":
                raise RuntimeError(f"Unknown statement kind '{statement.kind}'.")

            if not statement.should_jump:
                instruction_pointer += 1
                continue

            target = statement.argument or ""
            if Interpreter._parse_external_target(target) is not None:
                return
            instruction_pointer = labels[target]
