# Goto Language

`goto-language` is a deliberately tiny programming language where the **only
statement** is `goto`.

Labels (`<expression>:`) are declarations, and `goto` can jump to local labels
or cross-file targets (`goto <file>.goto` / `goto <file>.goto:<label>`).

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
7. `unless <expression>` may appear before goto and suppresses the jump when the expression evaluates to `True`.
8. Custom operators are supported in expressions: `~=` ("more or less") checks approximate equality and `=~` ("less is more") is the inverse.
9. The number of `not` modifiers changes behavior by toggling the jump decision: odd inverts it, even keeps it.
10. Expression results are converted to strings for label lookup at runtime (after sigils are acquired).
11. Duplicate label definitions are not allowed after expression resolution.
12. Local `goto` targets must refer to an existing resolved label.
13. A targetless `goto` pops the most recently encountered label and jumps to the new stack top.
14. Executing a targetless `goto` before any labels are encountered is a compile-time error.
15. Programs whose local control flow is provably infinite are rejected at compile time.
16. A trailing `;` is accepted at the end of non-empty statements.
17. Blank lines and lines beginning with `#` are ignored.
18. Sigils (`[name]`) are acquired on first use (prompted once, then cached globally) in both output text and goto expressions.
19. Backtick strings are accepted in expressions alongside single and double quotes.
20. A successful goto resolution collapses currently running threads to only that goto's resolved target threads.

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
