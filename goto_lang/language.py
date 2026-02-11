"""Core parser and interpreter for a language with only labels and goto statements."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instruction:
    """A single parsed instruction in the goto language.

    Attributes:
        op: Instruction opcode, currently only ``"goto"``.
        target: Target label for the jump.
        source_line: 1-based source line number in the original program.
    """

    op: str
    target: str
    source_line: int


@dataclass(frozen=True)
class Label:
    """A symbolic position marker in source code.

    Attributes:
        name: Label name without the trailing colon.
        instruction_index: Index into the instruction list where execution continues.
        source_line: 1-based source line number in the original program.
    """

    name: str
    instruction_index: int
    source_line: int


class ParseError(ValueError):
    """Raised when source code is not valid goto-language syntax."""


class RuntimeExecutionError(RuntimeError):
    """Raised when runtime execution cannot proceed."""


@dataclass(frozen=True)
class GotoProgram:
    """Parsed program and execution helper methods."""

    instructions: tuple[Instruction, ...]
    labels: dict[str, Label]

    def run(self, *, max_steps: int = 10_000) -> list[str]:
        """Execute the program.

        Args:
            max_steps: Maximum number of executed instructions before a safety stop.

        Returns:
            Ordered trace of visited labels and goto operations.

        Raises:
            RuntimeExecutionError: If a jump target does not exist.
            TimeoutError: If ``max_steps`` is exceeded, which usually means an infinite loop.
        """

        ip = 0
        steps = 0
        trace: list[str] = []
        while ip < len(self.instructions):
            if steps >= max_steps:
                raise TimeoutError(f"Execution exceeded max_steps={max_steps}")
            ins = self.instructions[ip]
            if ins.op != "goto":
                raise RuntimeExecutionError(f"Unsupported opcode: {ins.op}")
            label = self.labels.get(ins.target)
            if label is None:
                raise RuntimeExecutionError(
                    f"Line {ins.source_line}: unknown label '{ins.target}'"
                )
            trace.append(f"line {ins.source_line}: goto {ins.target}")
            ip = label.instruction_index
            steps += 1
        return trace

    def normalize(self) -> str:
        """Render a normalized source string from the parsed program.

        Returns:
            Canonicalized source where labels and instructions have one per line.
        """

        label_by_index: dict[int, list[Label]] = {}
        for label in self.labels.values():
            label_by_index.setdefault(label.instruction_index, []).append(label)

        lines: list[str] = []
        for idx in range(len(self.instructions) + 1):
            for label in sorted(label_by_index.get(idx, []), key=lambda item: item.name):
                lines.append(f"{label.name}:")
            if idx < len(self.instructions):
                ins = self.instructions[idx]
                lines.append(f"goto {ins.target}")
        return "\n".join(lines)


def parse_program(source: str) -> GotoProgram:
    """Parse a source string into a :class:`GotoProgram`.

    Syntax:
        - Empty lines and lines beginning with ``#`` are ignored.
        - ``label_name:`` declares a label.
        - ``goto label_name`` jumps to a label.

    Args:
        source: Full source text to parse.

    Returns:
        Parsed ``GotoProgram`` instance.

    Raises:
        ParseError: If source includes invalid or ambiguous syntax.
    """

    instructions: list[Instruction] = []
    labels: dict[str, Label] = {}

    for line_number, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.endswith(":"):
            label_name = line[:-1].strip()
            _validate_symbol(label_name, line_number)
            if label_name in labels:
                previous = labels[label_name]
                raise ParseError(
                    f"Line {line_number}: duplicate label '{label_name}' "
                    f"(first seen on line {previous.source_line})"
                )
            labels[label_name] = Label(
                name=label_name,
                instruction_index=len(instructions),
                source_line=line_number,
            )
            continue

        parts = line.split()
        if len(parts) == 2 and parts[0] == "goto":
            _validate_symbol(parts[1], line_number)
            instructions.append(
                Instruction(op="goto", target=parts[1], source_line=line_number)
            )
            continue

        raise ParseError(
            f"Line {line_number}: expected '<label>:' or 'goto <label>', got '{line}'"
        )

    return GotoProgram(instructions=tuple(instructions), labels=labels)


def _validate_symbol(symbol: str, line_number: int) -> None:
    """Validate labels and goto targets.

    Args:
        symbol: Identifier to validate.
        line_number: Line number for error reporting.

    Raises:
        ParseError: If identifier does not match language symbol rules.
    """

    if not symbol:
        raise ParseError(f"Line {line_number}: empty symbol is not allowed")

    if not (symbol[0].isalpha() or symbol[0] == "_"):
        raise ParseError(
            f"Line {line_number}: symbol '{symbol}' must start with a letter or underscore"
        )

    for char in symbol[1:]:
        if not (char.isalnum() or char == "_"):
            raise ParseError(
                f"Line {line_number}: symbol '{symbol}' contains invalid character '{char}'"
            )
