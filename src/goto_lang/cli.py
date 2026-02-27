"""Command-line interface for the goto-only language."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .interpreter import Interpreter
from .parser import ParseError


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for the CLI."""

    parser = argparse.ArgumentParser(
        prog="goto-lang",
        description="Run programs written in a language with only labels and goto.",
    )
    parser.add_argument("source", type=Path, help="Path to a .goto source file")
    parser.add_argument(
        "--max-steps",
        type=int,
        default=10_000,
        help="Stop execution after this many steps (default: 10000).",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Print executed source locations as file:line.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--check",
        action="store_true",
        help="Compile the source file without running it.",
    )
    mode_group.add_argument(
        "--inspect",
        action="store_true",
        help="Compile and print the normalized label and statement tables.",
    )
    return parser


def _render_program_inspection(runtime: Interpreter, source_path: Path) -> str:
    """Render a human-readable summary of compiled statements.

    Args:
        runtime: Interpreter used to compile source code.
        source_path: Path to source file that should be compiled.

    Returns:
        A formatted multi-line string with labels and statement listing.
    """

    program = runtime.compile_file(source_path)
    labels_rendered = ", ".join(
        f"{name}->{ip}" for name, ip in sorted(program.labels.items(), key=lambda item: item[1])
    )
    lines = [f"Labels: {labels_rendered or '<none>'}", "Statements:"]
    for index, statement in enumerate(program.statements):
        rendered_argument: object
        if statement.argument is None:
            rendered_argument = None
        elif statement.kind == "label":
            rendered_argument = statement.argument[0]
        elif len(statement.argument) == 1:
            rendered_argument = statement.argument[0]
        else:
            rendered_argument = list(statement.argument)

        jump_status = " jump" if statement.kind == "goto" and statement.should_jump else " no-jump"
        lines.append(
            f"  [{index}] {statement.kind} {rendered_argument!r}"
            f" line={statement.source_line}{jump_status if statement.kind == 'goto' else ''}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the goto-language CLI and return process exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)

    runtime = Interpreter()

    try:
        if args.check:
            runtime.compile_file(args.source)
            print("Check successful.")
            return 0

        if args.inspect:
            print(_render_program_inspection(runtime, args.source))
            return 0

        result = runtime.run_file(args.source, max_steps=args.max_steps)
    except ParseError as err:
        print(f"Parse error: {err}", file=sys.stderr)
        return 2

    status = "terminated" if result.terminated else "stopped"
    print(
        f"Program {status} after {result.steps} steps at instruction "
        f"pointer {result.instruction_pointer} ({result.reason})."
    )

    if args.trace:
        trace_rendered = ", ".join(f"{event.file}:{event.line}" for event in result.trace)
        print(f"Trace: [{trace_rendered}]")

    return 0 if result.terminated else 1


if __name__ == "__main__":
    raise SystemExit(main())
