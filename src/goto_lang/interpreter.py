"""Interpreter for the goto-only language."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .parser import FILE_REFERENCE_PATTERN, ParseError, ParsedLine, parse_program


@dataclass(frozen=True)
class Statement:
    """Executable representation of a source line."""

    kind: str
    argument: tuple[str, ...] | None
    source_line: int
    should_jump: bool = True


@dataclass(frozen=True)
class Program:
    """Compiled goto language program."""

    statements: list[Statement]
    labels: dict[str, int]
    label_stack: tuple[str, ...]


@dataclass(frozen=True)
class ExecutionResult:
    """Result of a program execution."""

    terminated: bool
    steps: int
    instruction_pointer: int
    reason: str
    trace: list[TraceEvent]


@dataclass(frozen=True)
class TraceEvent:
    """One executed source location in an execution trace."""

    file: str
    line: int


@dataclass
class ThreadState:
    """Mutable execution state for one runtime thread."""

    program: Program
    instruction_pointer: int
    current_path: Path | None
    label_stack: list[str]


class Interpreter:
    """Compiler and runtime for the goto-only language."""

    def compile(
        self,
        source: str,
        user_function: Callable[[str], object] | None = None,
    ) -> Program:
        """Compile source code into a :class:`Program`.

        Args:
            source: Source code to compile.

        Returns:
            Program: Compiled instructions and label table.

        Raises:
            ParseError: If syntax or label references are invalid.
        """

        parsed = parse_program(source, user_function=user_function)
        statements: list[Statement] = []
        labels: dict[str, int] = {}

        for line in parsed:
            self._append_statement(line, statements, labels)

        self._validate_goto_targets(statements, labels)
        self._validate_not_guaranteed_infinite(statements, labels, ())
        return Program(statements=statements, labels=labels, label_stack=())


    @staticmethod
    def _default_user(prompt: str) -> str:
        """Write a prompt and return one line of user input."""

        print(prompt, end="", flush=True)
        return input()

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

        program = self.compile(source, user_function=self._default_user)
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
        program = self.compile(source, user_function=self._default_user)
        return self._run_with_context(program, max_steps=max_steps, current_path=path)

    def compile_file(self, source_path: Path | str) -> Program:
        """Compile a program loaded from disk.

        Args:
            source_path: File path to source code.

        Returns:
            Program: Compiled instructions and label table.

        Raises:
            ParseError: If syntax or label references are invalid.
        """

        path = Path(source_path).resolve()
        source = path.read_text(encoding="utf-8")
        return self.compile(source)

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

        last_instruction_pointer = 0
        steps = 0
        trace: list[TraceEvent] = []
        default_trace_file = str(current_path) if current_path is not None else "<memory>"
        threads: list[ThreadState] = [
            ThreadState(
                program=program,
                instruction_pointer=0,
                current_path=current_path,
                label_stack=list(program.label_stack),
            )
        ]

        while threads:
            next_threads: list[ThreadState] = []
            for thread in threads:
                if steps >= max_steps:
                    return ExecutionResult(
                        terminated=False,
                        steps=steps,
                        instruction_pointer=thread.instruction_pointer,
                        reason=f"step limit reached ({max_steps})",
                        trace=trace,
                    )

                if thread.instruction_pointer >= len(thread.program.statements):
                    continue

                statement = thread.program.statements[thread.instruction_pointer]
                trace_file = (
                    str(thread.current_path)
                    if thread.current_path is not None
                    else default_trace_file
                )
                trace.append(TraceEvent(file=trace_file, line=statement.source_line))
                last_instruction_pointer = thread.instruction_pointer
                steps += 1

                if statement.kind == "label":
                    assert statement.argument is not None
                    thread.label_stack.append(statement.argument[0])
                    thread.instruction_pointer += 1
                    next_threads.append(thread)
                    continue

                if statement.kind == "noop":
                    thread.instruction_pointer += 1
                    next_threads.append(thread)
                    continue

                if statement.kind != "goto":
                    raise RuntimeError(f"Unknown statement kind '{statement.kind}'.")

                if not statement.should_jump:
                    self._discard_label_from_stack(thread.label_stack, statement.argument)
                    thread.instruction_pointer += 1
                    next_threads.append(thread)
                    continue

                targets = statement.argument
                if targets is None:
                    if not thread.label_stack:
                        raise ParseError(
                            f"Cannot execute targetless goto on line {statement.source_line} "
                            "before any labels are encountered."
                        )
                    thread.label_stack.pop()
                    target = thread.label_stack[-1] if thread.label_stack else None
                    if target is None:
                        thread.instruction_pointer += 1
                        next_threads.append(thread)
                        continue
                    targets = (target,)

                spawned_threads: list[ThreadState] = []
                for target in targets:
                    spawned_threads.append(
                        self._jump_to_target(thread, target)
                    )
                next_threads.extend(spawned_threads)

            threads = [
                thread
                for thread in next_threads
                if thread.instruction_pointer < len(thread.program.statements)
            ]

        return ExecutionResult(
            terminated=True,
            steps=steps,
            instruction_pointer=last_instruction_pointer,
            reason="completed",
            trace=trace,
        )

    @staticmethod
    def _discard_label_from_stack(label_stack: list[str], target: tuple[str, ...] | None) -> None:
        """Remove a pending local goto target from the runtime label stack.

        When a goto is disabled via ``not`` and the target label is already on the
        stack, the latest matching stack entry is removed without performing a jump.

        Args:
            label_stack: Runtime stack of encountered labels.
            target: Raw goto target argument from the source line.
        """

        if target is None:
            return

        for one_target in target:
            for idx in range(len(label_stack) - 1, -1, -1):
                if label_stack[idx] == one_target:
                    del label_stack[idx]
                    break

    @staticmethod
    def _discard_label_from_history(
        encountered_labels: tuple[str, ...],
        target: tuple[str, ...] | None,
    ) -> tuple[str, ...]:
        """Return label history with the newest matching label removed.

        Args:
            encountered_labels: Immutable history of visited labels.
            target: Local goto target that should be discarded.

        Returns:
            Updated tuple with the most recent target removed, or the original
            tuple when no matching label exists.
        """

        if target is None:
            return encountered_labels

        updated = encountered_labels
        for one_target in target:
            for idx in range(len(updated) - 1, -1, -1):
                if updated[idx] == one_target:
                    updated = updated[:idx] + updated[idx + 1 :]
                    break

        return updated

    def _jump_to_target(self, thread: ThreadState, target: str) -> ThreadState:
        """Return a thread state positioned at the target label."""

        current_path = thread.current_path
        if self._parse_external_target(target) is not None:
            external_target = self._parse_external_target(target)
            assert external_target is not None
            if current_path is None:
                raise ParseError("File-based goto requires execution from a file path.")
            new_program, new_ip, new_path = self._load_external_program(
                current_path,
                external_target[0],
                external_target[1],
            )
            return type(thread)(
                program=new_program,
                instruction_pointer=new_ip,
                current_path=new_path,
                label_stack=list(thread.label_stack),
            )

        return type(thread)(
            program=thread.program,
            instruction_pointer=thread.program.labels[target],
            current_path=current_path,
            label_stack=list(thread.label_stack),
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
                    argument=(line.label,),
                    source_line=line.index,
                )
            )
            return

        if line.is_goto:
            statements.append(
                Statement(
                    kind="goto",
                    argument=line.goto_targets,
                    should_jump=line.should_jump is not False,
                    source_line=line.index,
                )
            )
            return

        statements.append(
            Statement(
                kind="noop",
                argument=None,
                source_line=line.index,
            )
        )


    @staticmethod
    def _validate_goto_targets(
        statements: list[Statement], labels: dict[str, int]
    ) -> None:
        """Ensure each goto instruction references a known local label or file target."""

        for statement in statements:
            if statement.kind != "goto":
                continue
            if statement.argument is None:
                continue
            for target in statement.argument:
                if target in labels:
                    continue
                if Interpreter._parse_external_target(target) is not None:
                    continue
                raise ParseError(
                    f"Unknown label '{target}' referenced "
                    f"on line {statement.source_line}."
                )

    @staticmethod
    def _validate_not_guaranteed_infinite(
        statements: list[Statement],
        labels: dict[str, int],
        label_stack: tuple[str, ...],
    ) -> None:
        """Reject programs whose local control flow is provably non-terminating."""

        del label_stack

        if not statements:
            return

        has_multi_target_goto = any(
            statement.kind == "goto"
            and statement.argument is not None
            and len(statement.argument) > 1
            for statement in statements
        )
        if has_multi_target_goto:
            return

        has_targetless_goto = any(
            statement.kind == "goto" and statement.argument is None
            for statement in statements
        )
        if not has_targetless_goto:
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
                if statement.kind in {"label", "noop"}:
                    instruction_pointer += 1
                    continue
                if statement.kind != "goto":
                    raise RuntimeError(f"Unknown statement kind '{statement.kind}'.")
                if not statement.should_jump:
                    instruction_pointer += 1
                    continue
                target = statement.argument[0] if statement.argument else ""
                if Interpreter._parse_external_target(target) is not None:
                    return
                instruction_pointer = labels[target]
            return

        seen_states: set[tuple[int, tuple[str, ...]]] = set()
        instruction_pointer = 0
        encountered_labels: tuple[str, ...] = ()

        analysis_steps = 0
        max_analysis_steps = max(1, len(statements) * 100)

        while instruction_pointer < len(statements):
            analysis_steps += 1
            if analysis_steps > max_analysis_steps:
                looping_statement = statements[instruction_pointer]
                raise ParseError(
                    "Infinite loop detected at "
                    f"line {looping_statement.source_line}."
                )

            state = (instruction_pointer, encountered_labels)
            if state in seen_states:
                looping_statement = statements[instruction_pointer]
                raise ParseError(
                    "Infinite loop detected at "
                    f"line {looping_statement.source_line}."
                )
            seen_states.add(state)

            statement = statements[instruction_pointer]
            if statement.kind == "label":
                assert statement.argument is not None
                encountered_labels = (*encountered_labels, statement.argument[0])
                instruction_pointer += 1
                continue

            if statement.kind == "noop":
                instruction_pointer += 1
                continue

            if statement.kind != "goto":
                raise RuntimeError(f"Unknown statement kind '{statement.kind}'.")

            if not statement.should_jump:
                encountered_labels = Interpreter._discard_label_from_history(
                    encountered_labels,
                    statement.argument,
                )
                instruction_pointer += 1
                continue

            targets = statement.argument
            if targets is None:
                if not encountered_labels:
                    raise ParseError(
                        f"Cannot execute targetless goto on line {statement.source_line} "
                        "before any labels are encountered."
                    )
                encountered_labels = encountered_labels[:-1]
                target = encountered_labels[-1] if encountered_labels else None
                if target is None:
                    instruction_pointer += 1
                    continue
            else:
                target = targets[0]

            if target is None:
                instruction_pointer += 1
                continue
            if Interpreter._parse_external_target(target) is not None:
                return
            instruction_pointer = labels[target]
