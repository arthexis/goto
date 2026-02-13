# Goto Language

`goto-language` is a deliberately tiny programming language where the **only**
allowed constructs are:

- label definitions (`<expression>:`)
- unconditional jumps (`goto <expression>` / `go to <expression>`)
- cross-file jumps (`goto <file>.goto` or `goto <file>.goto:<label>`)

It includes a parser, compiler/runtime, and CLI.

## Syntax

```text
start:
  goto loop
loop:
  goto loop
```

Rules:

1. Label declarations and `goto` targets are expressions.
2. Supported expressions are intentionally limited to:
   - constants (`"text"`, `123`, `4.5`, `True`, `False`, `None`)
   - unary numeric `+` / `-`
   - binary arithmetic `+`, `-`, `*`, `/`, `//`, `%`, `**`
   - string concatenation via `"a" + "b"`
3. Bare labels like `start` are still accepted directly, and `goto` also supports file targets (`<file>.goto`, `<file>.goto:<label>`, and `<file>.goto <label>`).
4. Names, function calls, attribute access, comprehensions, imports, and other Python syntax are rejected.
5. `goto` may be written as `goto` or `go to` in any case.
6. Optional words `do`, `please`, and `not` may appear before goto in any order.
7. The number of `not` modifiers changes behavior: odd means no jump, even means jump.
8. Expression results are converted to strings for label lookup.
9. Duplicate label definitions are not allowed after expression resolution.
10. Local `goto` targets must refer to an existing resolved label.
11. Programs whose local control flow is provably infinite are rejected at compile time.
12. Blank lines and lines beginning with `#` are ignored.

## Running

Install in editable mode:

```bash
pip install -e .
```

Run a program:

```bash
goto-lang examples/loop.goto --max-steps 20 --trace
```

Compile-check without running:

```bash
goto-lang examples/terminate.goto --check
```

Exit codes:

- `0`: successful run termination, or successful `--check` compilation.
- `1`: execution stopped due to step limit (run mode only).
- `2`: parse/compile error (including `--check`).

## Development

Install in editable mode with test tooling:

```bash
pip install -e .
```

Run tests:

```bash
pytest -q
```

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE) for details.

## Design notes

Because the language has only labels and unconditional jumps, control flow is
explicit and there is no mutable state in the core language.

## Backward compatibility notes

- Trace output now reports source locations as `file:line` entries instead of plain line numbers.
- In-memory execution via `Interpreter.run(...)` uses `"<memory>"` as the trace file sentinel.
