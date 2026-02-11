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
        help="Print executed source line numbers.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the goto-language CLI and return process exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)

    runtime = Interpreter()

    try:
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
        trace_rendered = ", ".join(str(line) for line in result.trace)
        print(f"Trace: [{trace_rendered}]")

    return 0 if result.terminated else 1


if __name__ == "__main__":
    raise SystemExit(main())
