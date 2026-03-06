"""Command-line interface for the goto-only language."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from .interpreter import Interpreter, LLMProvider
from .parser import ParseError


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for the CLI."""

    parser = argparse.ArgumentParser(
        prog="goto-lang",
        description="Run programs written in a language with only labels and goto.",
    )
    parser.add_argument("source", type=Path, help="Path to a .goto source file")
    parser.add_argument("--max-steps", type=int, default=10_000, help="Stop execution after this many steps (default: 10000).")
    parser.add_argument("--trace", action="store_true", help="Print executed source locations as file:line.")
    parser.add_argument("--llm-model", help="Use this LLM model for non-interactive yes/no and sigil prompts.")
    parser.add_argument("--llm-api-key", help="API key used for hosted LLM APIs.")
    parser.add_argument("--llm-base-url", default="https://api.openai.com/v1", help="Base URL for chat completions (OpenAI-compatible).")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--check", action="store_true", help="Compile the source file without running it.")
    mode_group.add_argument("--inspect", action="store_true", help="Compile and print the normalized label and statement tables.")
    return parser


def _render_program_inspection(runtime: Interpreter, source_path: Path) -> str:
    """Render a human-readable summary of compiled statements."""

    program = runtime.compile_file(source_path)
    labels_rendered = ", ".join(f"{name}->{ip}" for name, ip in sorted(program.labels.items(), key=lambda item: item[1]))
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

        lines.append(
            f"  [{index}] {statement.kind} {rendered_argument!r} line={statement.source_line}"
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

        provider = None
        if args.llm_model:
            provider = LLMProvider(
                model=args.llm_model,
                api_key=args.llm_api_key or os.getenv("TOKEN_API_KEY") or os.getenv("OPENAI_API_KEY"),
                base_url=args.llm_base_url,
            )

        result = runtime.run_file(args.source, max_steps=args.max_steps, provider=provider)
    except ParseError as err:
        print(f"Parse error: {err}", file=sys.stderr)
        return 2

    status = "terminated" if result.terminated else "stopped"
    print(f"Program {status} after {result.steps} steps at instruction pointer {result.instruction_pointer} ({result.reason}).")

    if args.trace:
        trace_rendered = ", ".join(f"{event.file}:{event.line}" for event in result.trace)
        print(f"Trace: [{trace_rendered}]")

    return 0 if result.terminated else 1


if __name__ == "__main__":
    raise SystemExit(main())
