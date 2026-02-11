# Goto Language

`goto-language` is a deliberately tiny programming language where the **only**
allowed constructs are:

- label definitions (`<expression>:`)
- unconditional jumps (`goto <expression>` / `go to <expression>`)

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
2. `goto` may be written as `goto` or `go to` in any case.
3. Optional words `do`, `please`, and `not` may appear before goto in any order.
4. The number of `not` modifiers changes behavior: odd means no jump, even means jump.
5. Expression results are converted to strings for label lookup.
6. Duplicate label definitions are not allowed after expression resolution.
7. `goto` targets must refer to an existing resolved label.
8. Blank lines and lines beginning with `#` are ignored.

## Running

Install in editable mode:

```bash
pip install -e .
```

Run a program:

```bash
goto-lang examples/loop.goto --max-steps 20 --trace
```

Exit codes:

- `0`: program terminated by falling past the final statement.
- `1`: execution stopped due to step limit.
- `2`: parse/compile error.

## Design notes

Because the language has only labels and unconditional jumps, control flow is
explicit and there is no mutable state in the core language.
