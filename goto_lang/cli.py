"""Command line interface for the goto-only language."""

from __future__ import annotations

import argparse
from pathlib import Path

from .language import ParseError, RuntimeExecutionError, parse_program


def build_parser() -> argparse.ArgumentParser:
    """Create and configure CLI argument parser."""

    parser = argparse.ArgumentParser(
        prog="goto-lang",
        description="Run or normalize programs in a language with only labels and goto.",
    )
    parser.add_argument("file", type=Path, help="Path to source program file")
    parser.add_argument(
        "--print-normalized",
        action="store_true",
        help="Print normalized source instead of running the program",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=10_000,
        help="Execution safety limit for goto steps",
    )
    return parser


def main() -> int:
    """Run the CLI entrypoint.

    Returns:
        Process exit code.
    """

    parser = build_parser()
    args = parser.parse_args()

    try:
        source = args.file.read_text(encoding="utf-8")
        program = parse_program(source)

        if args.print_normalized:
            print(program.normalize())
            return 0

        trace = program.run(max_steps=args.max_steps)
        for step in trace:
            print(step)
        return 0
    except FileNotFoundError:
        parser.error(f"File not found: {args.file}")
    except (ParseError, RuntimeExecutionError, TimeoutError) as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
